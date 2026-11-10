"""Create or edit a promotion and its rule from the dashboard.

A promotion can hold several rules (the engine applies the first that matches);
the form edits the first and leaves any others as they are.
"""

from __future__ import annotations

from decimal import Decimal

from django.utils.text import slugify

from morpheus.app import forms

KINDS = [
    ('percent_off', 'Percent off the cart'),
    ('fixed_off', 'Amount off the cart'),
    ('free_shipping', 'Free shipping'),
    ('gift', 'Free gift'),
    ('bogo', 'Buy X get Y'),
    ('tiered', 'Buy more, save more'),
]


def _tokens(text: str) -> list[str]:
    return [t.strip() for t in (text or '').replace('\n', ',').split(',') if t.strip()]


def _find_products(tokens):
    """Products by SKU (the product's or a variant's) or slug; returns
    ``(products, unknown_tokens)``."""
    from django.db.models import Q

    from plugins.installed.catalog.models import Product

    found, unknown = [], []
    for tok in tokens:
        product = (
            Product.objects.filter(Q(sku__iexact=tok) | Q(slug=tok) | Q(variants__sku__iexact=tok))
            .distinct()
            .first()
        )
        if product is None:
            unknown.append(tok)
        elif product not in found:
            found.append(product)
    return found, unknown


def parse_tiers(text: str) -> list[dict]:
    """``"3:10, 5:15"`` → ``[{'min_qty': 3, 'percent': 10}, …]``."""
    tiers = []
    for tok in _tokens(text):
        qty, _, pct = tok.partition(':')
        try:
            tiers.append({'min_qty': int(qty), 'percent': float(Decimal(pct.strip()))})
        except (ValueError, ArithmeticError) as exc:
            raise forms.ValidationError(
                f'"{tok}" is not "items:percent", for example 3:10.'
            ) from exc
    return tiers


class PromotionForm(forms.Form):
    name = forms.CharField(max_length=200)
    slug = forms.SlugField(max_length=200, required=False)
    description = forms.CharField(widget=forms.Textarea, required=False)
    is_active = forms.BooleanField(required=False, initial=True)
    combinable = forms.BooleanField(required=False, initial=True)
    priority = forms.IntegerField(initial=100)
    starts_at = forms.DateTimeField(required=False)
    ends_at = forms.DateTimeField(required=False)
    requires_coupon = forms.CharField(max_length=64, required=False)
    usage_limit = forms.IntegerField(min_value=1, required=False)

    kind = forms.ChoiceField(choices=KINDS)
    value = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)
    buy_qty = forms.IntegerField(min_value=1, required=False)
    free_qty = forms.IntegerField(min_value=1, required=False)
    gift_product = forms.CharField(max_length=200, required=False)
    tiers = forms.CharField(required=False)

    min_subtotal = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0, required=False)
    max_subtotal = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0, required=False)
    countries = forms.CharField(max_length=500, required=False)
    customer_groups = forms.CharField(max_length=500, required=False)
    products = forms.CharField(required=False)
    categories = forms.MultipleChoiceField(required=False, choices=())
    first_order = forms.BooleanField(required=False)

    def __init__(self, *args, instance=None, **kwargs):
        from plugins.installed.catalog.category_tree import display_tree

        self.instance = instance
        self.rule = instance.rules.first() if instance is not None else None
        if instance is not None and 'initial' not in kwargs:
            kwargs['initial'] = self._initial(instance, self.rule)
        super().__init__(*args, **kwargs)
        self.fields['categories'].choices = [
            (c.slug, ('— ' * c.depth) + c.name) for c in display_tree()
        ]

    @staticmethod
    def _initial(promo, rule) -> dict:
        from plugins.installed.catalog.models import Product

        action = (rule.action if rule else {}) or {}
        pred = (rule.predicates if rule else {}) or {}
        gift = ''
        if action.get('product_id'):
            p = Product.objects.filter(pk=action['product_id']).first()
            gift = (p.sku or p.slug) if p else ''
        products = Product.objects.filter(pk__in=pred.get('product_ids') or [])
        return {
            'name': promo.name,
            'slug': promo.slug,
            'description': promo.description,
            'is_active': promo.is_active,
            'combinable': promo.combinable,
            'priority': promo.priority,
            'starts_at': promo.starts_at,
            'ends_at': promo.ends_at,
            'requires_coupon': promo.requires_coupon,
            'usage_limit': promo.usage_limit,
            'kind': action.get('kind') or 'percent_off',
            'value': action.get('value', action.get('percent')),
            'buy_qty': action.get('buy_qty'),
            'free_qty': action.get('free_qty'),
            'gift_product': gift,
            'tiers': ', '.join(
                f'{t["min_qty"]}:{t["percent"]:g}' for t in action.get('tiers') or []
            ),
            'min_subtotal': pred.get('min_subtotal'),
            'max_subtotal': pred.get('max_subtotal'),
            'countries': ', '.join(pred.get('countries') or []),
            'customer_groups': ', '.join(pred.get('customer_groups') or []),
            'products': ', '.join(p.sku or p.slug for p in products),
            'categories': list(pred.get('category_slugs') or []),
            'first_order': bool(pred.get('first_order')),
        }

    def clean_slug(self):
        from plugins.installed.promotions.models import Promotion

        slug = self.cleaned_data.get('slug') or slugify(self.data.get('name') or '')[:200]
        if not slug:
            raise forms.ValidationError('Give the promotion a name.')
        qs = Promotion.objects.filter(slug=slug)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Another promotion already uses this slug.')
        return slug

    def clean(self):  # noqa: PLR0912 — one check per kind
        cd = super().clean()
        kind = cd.get('kind')
        value = cd.get('value')
        if kind == 'percent_off' and not (value and 0 < value <= 100):
            self.add_error('value', 'Enter a percent between 0 and 100.')
        if kind == 'fixed_off' and not value:
            self.add_error('value', 'Enter the amount to take off.')
        if kind == 'bogo' and value is not None and value > 100:
            self.add_error('value', 'Enter a percent up to 100, or leave it empty for free.')
        if kind == 'gift':
            found, unknown = _find_products(_tokens(cd.get('gift_product') or ''))
            if unknown or len(found) != 1:
                self.add_error('gift_product', 'Enter the SKU or slug of one product.')
            else:
                cd['_gift'] = found[0]
        if kind == 'tiered':
            try:
                cd['_tiers'] = parse_tiers(cd.get('tiers') or '')
            except forms.ValidationError as e:
                self.add_error('tiers', e)
            else:
                if not cd['_tiers']:
                    self.add_error('tiers', 'Add at least one tier, for example 3:10.')
        found, unknown = _find_products(_tokens(cd.get('products') or ''))
        if unknown:
            self.add_error('products', f'No product with SKU or slug: {", ".join(unknown)}.')
        cd['_products'] = found
        if cd.get('starts_at') and cd.get('ends_at') and cd['ends_at'] <= cd['starts_at']:
            self.add_error('ends_at', 'The end must be after the start.')
        return cd

    def _action(self, cd) -> dict:
        kind = cd['kind']
        if kind in ('percent_off', 'fixed_off'):
            return {'kind': kind, 'value': float(cd['value'])}
        if kind == 'gift':
            return {'kind': 'gift', 'product_id': str(cd['_gift'].pk)}
        if kind == 'bogo':
            action = {
                'kind': 'bogo',
                'buy_qty': cd.get('buy_qty') or 2,
                'free_qty': cd.get('free_qty') or 1,
                'product_ids': [str(p.pk) for p in cd['_products']],
            }
            if cd.get('value'):
                action['percent'] = float(cd['value'])
            return action
        if kind == 'tiered':
            return {'kind': 'tiered', 'tiers': cd['_tiers']}
        return {'kind': kind}

    def _predicates(self, cd) -> dict:
        pred: dict = {}
        if cd.get('min_subtotal'):
            pred['min_subtotal'] = float(cd['min_subtotal'])
        if cd.get('max_subtotal'):
            pred['max_subtotal'] = float(cd['max_subtotal'])
        if _tokens(cd.get('countries') or ''):
            pred['countries'] = [c.upper() for c in _tokens(cd['countries'])]
        if _tokens(cd.get('customer_groups') or ''):
            pred['customer_groups'] = _tokens(cd['customer_groups'])
        # A buy-X-get-Y rule uses its products as the set it counts; for every
        # other kind they are a condition (the cart must hold one).
        if cd['_products'] and cd['kind'] != 'bogo':
            pred['product_ids'] = [str(p.pk) for p in cd['_products']]
        if cd.get('categories'):
            pred['category_slugs'] = list(cd['categories'])
        if cd.get('first_order'):
            pred['first_order'] = True
        return pred

    def save(self):
        from plugins.installed.promotions.models import Promotion, PromotionRule

        cd = self.cleaned_data
        promo = self.instance or Promotion()
        promo.name = cd['name']
        promo.slug = cd['slug']
        promo.description = cd.get('description') or ''
        promo.is_active = bool(cd.get('is_active'))
        promo.combinable = bool(cd.get('combinable'))
        promo.priority = cd['priority']
        promo.starts_at = cd.get('starts_at')
        promo.ends_at = cd.get('ends_at')
        promo.requires_coupon = (cd.get('requires_coupon') or '').strip()
        promo.usage_limit = cd.get('usage_limit')
        promo.save()
        rule = self.rule or PromotionRule(promotion=promo)
        rule.action = self._action(cd)
        rule.predicates = self._predicates(cd)
        rule.save()
        return promo

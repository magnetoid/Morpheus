"""Marketing forms: coupon create/edit."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from morpheus.app import forms

from ._helpers import _money


class CouponForm(forms.Form):
    """Create/edit a `marketing.Coupon`."""

    code = forms.CharField(max_length=50)
    name = forms.CharField(max_length=200)
    description = forms.CharField(widget=forms.Textarea, required=False)
    discount_type = forms.ChoiceField(
        choices=[
            ('percentage', 'Percentage'),
            ('fixed_amount', 'Fixed amount'),
            ('free_shipping', 'Free shipping'),
            ('buy_x_get_y', 'Buy X get Y'),
        ]
    )
    discount_value = forms.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    minimum_order_amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0'),
        required=False,
    )
    maximum_discount_amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal('0'),
        required=False,
    )
    usage_limit = forms.IntegerField(min_value=0, required=False)
    usage_limit_per_customer = forms.IntegerField(min_value=0, required=False)
    is_active = forms.BooleanField(required=False, initial=True)
    starts_at = forms.DateTimeField(required=False)
    expires_at = forms.DateTimeField(required=False)

    # Where it applies (marketing/scope.py reads these at checkout).
    applicable_products = forms.CharField(required=False)
    applicable_categories = forms.MultipleChoiceField(required=False, choices=())
    applicable_collections = forms.MultipleChoiceField(required=False, choices=())
    exclude_sale_items = forms.BooleanField(required=False)
    buy_quantity = forms.IntegerField(min_value=1, required=False)
    get_quantity = forms.IntegerField(min_value=1, required=False)

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        if instance is not None and 'initial' not in kwargs:
            kwargs['initial'] = {
                'code': instance.code,
                'name': instance.name,
                'description': instance.description,
                'discount_type': instance.discount_type,
                'discount_value': instance.discount_value,
                'minimum_order_amount': (
                    instance.minimum_order_amount.amount if instance.minimum_order_amount else None
                ),
                'maximum_discount_amount': (
                    instance.maximum_discount_amount.amount
                    if instance.maximum_discount_amount
                    else None
                ),
                'usage_limit': instance.usage_limit,
                'usage_limit_per_customer': instance.usage_limit_per_customer,
                'is_active': instance.is_active,
                'starts_at': instance.starts_at,
                'expires_at': instance.expires_at,
                'applicable_products': ', '.join(
                    p.sku or p.slug for p in instance.applicable_products.all()
                ),
                'applicable_categories': [
                    str(pk) for pk in instance.applicable_categories.values_list('pk', flat=True)
                ],
                'applicable_collections': [
                    str(pk) for pk in instance.applicable_collections.values_list('pk', flat=True)
                ],
                'exclude_sale_items': instance.exclude_sale_items,
                'buy_quantity': instance.buy_quantity,
                'get_quantity': instance.get_quantity,
            }
        super().__init__(*args, **kwargs)
        from plugins.installed.catalog.category_tree import display_tree
        from plugins.installed.catalog.models import Collection

        self.fields['applicable_categories'].choices = [
            (str(c.pk), ('— ' * c.depth) + c.name) for c in display_tree()
        ]
        self.fields['applicable_collections'].choices = [
            (str(c.pk), c.name) for c in Collection.objects.order_by('name')
        ]

    def clean_applicable_products(self):
        from django.db.models import Q

        from plugins.installed.catalog.models import Product

        tokens = [
            t.strip()
            for t in (self.cleaned_data.get('applicable_products') or '')
            .replace('\n', ',')
            .split(',')
            if t.strip()
        ]
        found, unknown = [], []
        for tok in tokens:
            product = (
                Product.objects.filter(
                    Q(sku__iexact=tok) | Q(slug=tok) | Q(variants__sku__iexact=tok)
                )
                .distinct()
                .first()
            )
            if product is None:
                unknown.append(tok)
            elif product not in found:
                found.append(product)
        if unknown:
            raise forms.ValidationError(f'No product with SKU or slug: {", ".join(unknown)}.')
        return found

    def clean(self):
        cd = super().clean()
        if cd.get('discount_type') == 'buy_x_get_y' and (cd.get('discount_value') or 0) > 100:
            self.add_error(
                'discount_value', 'For Buy X get Y, enter the percent off the Y items (100 = free).'
            )
        return cd

    def clean_code(self):
        code = self.cleaned_data['code'].strip().upper()
        if not code:
            raise forms.ValidationError('Code is required.')
        # marketing is optional (ADR 0013): only touch its table while enabled.
        from plugins.registry import app_registry

        if app_registry.is_active('marketing'):
            from plugins.installed.marketing.models import Coupon

            qs = Coupon.objects.filter(code=code)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError('Another coupon already uses this code.')
        return code

    def save(self) -> Any:
        from plugins.registry import app_registry

        if not app_registry.is_active('marketing'):
            raise ValueError('CouponForm.save() requires the marketing app.')
        from plugins.installed.marketing.models import Coupon

        cd = self.cleaned_data
        coupon = self.instance or Coupon()
        coupon.code = cd['code']
        coupon.name = cd['name']
        coupon.description = cd.get('description') or ''
        coupon.discount_type = cd['discount_type']
        coupon.discount_value = cd['discount_value']
        coupon.minimum_order_amount = _money(cd.get('minimum_order_amount'))
        coupon.maximum_discount_amount = _money(cd.get('maximum_discount_amount'))
        coupon.usage_limit = cd.get('usage_limit')
        coupon.usage_limit_per_customer = cd.get('usage_limit_per_customer')
        coupon.is_active = bool(cd.get('is_active'))
        coupon.starts_at = cd.get('starts_at')
        coupon.expires_at = cd.get('expires_at')
        coupon.exclude_sale_items = bool(cd.get('exclude_sale_items'))
        coupon.buy_quantity = cd.get('buy_quantity') or 1
        coupon.get_quantity = cd.get('get_quantity') or 1
        coupon.save()
        coupon.applicable_products.set(cd.get('applicable_products') or [])
        coupon.applicable_categories.set(cd.get('applicable_categories') or [])
        coupon.applicable_collections.set(cd.get('applicable_collections') or [])
        return coupon

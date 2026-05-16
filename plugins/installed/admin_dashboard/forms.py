"""Forms backing the admin dashboard create/edit pages.

Plain `forms.Form` subclasses (not ModelForms) so the rendering stays
fully under our control — we never want the Django admin look-and-feel
to leak into the merchant UI. Each form has a `save()` that handles
its own ORM writes and returns the persisted object.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from morpheus import forms
from django.utils.text import slugify


def _money(amount: str | Decimal | None, currency: str = 'USD'):
    """Return a djmoney `Money` from a raw string, or None if blank."""
    from djmoney.money import Money
    if amount in (None, ''):
        return None
    try:
        return Money(Decimal(str(amount)), currency)
    except (InvalidOperation, TypeError, ValueError):
        return None


import re as _re
_HTML_TAG_RE = _re.compile(r'<\w+[\s>]')


def _ensure_html(value: str | None) -> str:
    """Return HTML, converting legacy Markdown when needed.

    The TipTap editor expects HTML, but `populate_descriptions` historically
    wrote Markdown to `Product.{short_description,description}`. We convert
    on read so the editor renders the saved content correctly. Idempotent:
    rows that already look like HTML pass through unchanged.
    """
    if not value:
        return value or ''
    if _HTML_TAG_RE.search(value):
        return value
    from core.templatetags.morph import markdown_to_html
    return markdown_to_html(value)


# ── Product ──────────────────────────────────────────────────────────────────


class ProductForm(forms.Form):
    """Create/edit a `catalog.Product`. Variants/images live in their own flows."""

    name = forms.CharField(max_length=300)
    sku = forms.CharField(max_length=100, required=False)
    status = forms.ChoiceField(choices=[
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('archived', 'Archived'),
    ])
    product_type = forms.ChoiceField(choices=[
        ('simple', 'Simple'),
        ('variable', 'Variable'),
        ('digital', 'Digital'),
        ('bundle', 'Bundle'),
    ], initial='simple')
    price = forms.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'))
    compare_at_price = forms.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False,
    )
    cost_price = forms.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False,
    )
    short_description = forms.CharField(widget=forms.Textarea, required=False)
    description = forms.CharField(widget=forms.Textarea, required=False)
    category = forms.UUIDField(required=False)
    vendor = forms.UUIDField(required=False)
    is_featured = forms.BooleanField(required=False)
    is_taxable = forms.BooleanField(required=False, initial=True)
    track_inventory = forms.BooleanField(required=False, initial=True)
    requires_shipping = forms.BooleanField(required=False, initial=True)
    weight = forms.DecimalField(
        max_digits=8, decimal_places=3, required=False, min_value=Decimal('0'),
    )
    weight_unit = forms.CharField(max_length=5, required=False, initial='kg')

    # Digital products: file upload + delivery toggles. Only persisted
    # when product_type == 'digital'; the front-end hides this section
    # for non-digital products.
    digital_file = forms.FileField(required=False)
    digital_file_clear = forms.BooleanField(required=False)

    # ── SEO — basic ─────────────────────────────────────────────────────
    meta_title = forms.CharField(max_length=200, required=False)
    meta_description = forms.CharField(widget=forms.Textarea, required=False)
    focus_keyword = forms.CharField(max_length=120, required=False)
    canonical_url = forms.URLField(required=False)
    # ── SEO — Open Graph (og_image is uploaded separately) ──────────────
    og_title = forms.CharField(max_length=200, required=False)
    og_description = forms.CharField(widget=forms.Textarea, required=False)
    # ── SEO — Twitter Card ──────────────────────────────────────────────
    twitter_title = forms.CharField(max_length=200, required=False)
    twitter_description = forms.CharField(widget=forms.Textarea, required=False)
    twitter_card = forms.ChoiceField(choices=[
        ('summary', 'Summary'),
        ('summary_large_image', 'Summary with large image'),
    ], required=False, initial='summary_large_image')
    # ── SEO — crawler controls ──────────────────────────────────────────
    noindex = forms.BooleanField(required=False)
    nofollow = forms.BooleanField(required=False)
    # ── SEO — extra structured data (JSON; loose-typed for flexibility) ─
    structured_data = forms.CharField(
        widget=forms.Textarea, required=False,
        help_text='Optional JSON object merged into auto-generated JSON-LD.',
    )

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        if instance is not None and 'initial' not in kwargs:
            import json
            kwargs['initial'] = {
                'name': instance.name,
                'sku': instance.sku,
                'status': instance.status,
                'product_type': instance.product_type,
                'price': instance.price.amount if instance.price else None,
                'compare_at_price': (
                    instance.compare_at_price.amount if instance.compare_at_price else None
                ),
                'cost_price': (
                    instance.cost_price.amount if instance.cost_price else None
                ),
                # TipTap stores HTML; legacy rows from populate_descriptions
                # are Markdown — convert on read so the editor renders them.
                'short_description': _ensure_html(instance.short_description),
                'description': _ensure_html(instance.description),
                'category': instance.category_id,
                'vendor': instance.vendor_id,
                'is_featured': instance.is_featured,
                'is_taxable': instance.is_taxable,
                'track_inventory': instance.track_inventory,
                'requires_shipping': instance.requires_shipping,
                'weight': instance.weight,
                'weight_unit': instance.weight_unit,
                # SEO
                'meta_title': instance.meta_title,
                'meta_description': instance.meta_description,
                'focus_keyword': getattr(instance, 'focus_keyword', '') or '',
                'canonical_url': getattr(instance, 'canonical_url', '') or '',
                'og_title': getattr(instance, 'og_title', '') or '',
                'og_description': getattr(instance, 'og_description', '') or '',
                'twitter_title': getattr(instance, 'twitter_title', '') or '',
                'twitter_description': getattr(instance, 'twitter_description', '') or '',
                'twitter_card': getattr(instance, 'twitter_card', '') or 'summary_large_image',
                'noindex': bool(getattr(instance, 'noindex', False)),
                'nofollow': bool(getattr(instance, 'nofollow', False)),
                'structured_data': (
                    json.dumps(instance.structured_data, indent=2)
                    if getattr(instance, 'structured_data', None) else ''
                ),
            }
        super().__init__(*args, **kwargs)

    def clean_structured_data(self):
        raw = (self.cleaned_data.get('structured_data') or '').strip()
        if not raw:
            return {}
        import json
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as e:
            raise forms.ValidationError(f'Not valid JSON: {e}')
        if not isinstance(value, dict):
            raise forms.ValidationError('Structured data must be a JSON object.')
        return value

    def clean_sku(self):
        sku = (self.cleaned_data.get('sku') or '').strip()
        if not sku:
            return ''
        from plugins.installed.catalog.models import Product
        qs = Product.objects.filter(sku=sku)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Another product already uses this SKU.')
        return sku

    def save(self) -> Any:
        from plugins.installed.catalog.models import Product, Category, Vendor

        cd = self.cleaned_data
        product = self.instance or Product()
        product.name = cd['name']
        product.sku = cd['sku'] or ''
        product.status = cd['status']
        product.product_type = cd['product_type']
        product.price = _money(cd['price']) or product.price
        product.compare_at_price = _money(cd.get('compare_at_price'))
        product.cost_price = _money(cd.get('cost_price'))
        product.short_description = cd.get('short_description') or ''
        product.description = cd.get('description') or ''
        product.is_featured = bool(cd.get('is_featured'))
        product.is_taxable = bool(cd.get('is_taxable'))
        product.track_inventory = bool(cd.get('track_inventory'))
        product.requires_shipping = bool(cd.get('requires_shipping'))
        product.weight = cd.get('weight')
        product.weight_unit = cd.get('weight_unit') or 'kg'

        # SEO fields — only assign when the model actually has them so
        # this code keeps working against an older Product schema.
        for field in (
            'meta_title', 'meta_description', 'focus_keyword',
            'canonical_url', 'og_title', 'og_description',
            'twitter_title', 'twitter_description', 'twitter_card',
        ):
            if hasattr(product, field):
                setattr(product, field, cd.get(field) or '')
        for flag in ('noindex', 'nofollow'):
            if hasattr(product, flag):
                setattr(product, flag, bool(cd.get(flag)))
        if hasattr(product, 'structured_data'):
            product.structured_data = cd.get('structured_data') or {}

        if cd.get('category'):
            product.category = Category.objects.filter(pk=cd['category']).first()
        else:
            product.category = None
        if cd.get('vendor'):
            product.vendor = Vendor.objects.filter(pk=cd['vendor']).first()
        else:
            product.vendor = None

        # Digital products don't ship — force the related flags off so a
        # merchant can't accidentally save a digital product as needing
        # shipping (and so tax/shipping calculation paths skip them).
        if cd['product_type'] == 'digital':
            product.requires_shipping = False
            product.weight = None
            product.weight_unit = ''

        # Digital file: upload, clear, or leave alone. Only meaningful
        # when the product is digital — otherwise we ignore it (so
        # toggling type doesn't unexpectedly drop the file).
        if hasattr(product, 'digital_file') and cd['product_type'] == 'digital':
            if cd.get('digital_file_clear'):
                if product.digital_file:
                    product.digital_file.delete(save=False)
                product.digital_file = None
            new_file = self.files.get('digital_file') if hasattr(self, 'files') else None
            if new_file:
                product.digital_file = new_file

        if not product.slug:
            product.slug = slugify(product.name)[:300] or 'product'
        product.save()
        return product


# ── Customer ─────────────────────────────────────────────────────────────────


class CustomerForm(forms.Form):
    """Create/edit a `customers.Customer` (a.k.a. Contact in the dashboard).

    `source` marks where the contact arrived from — orders, lead form,
    signup, etc. `company` is exposed so B2B contacts captured via the
    storefront or CRM lead form land in the same record without
    needing a separate Lead row.
    """

    email = forms.EmailField()
    first_name = forms.CharField(max_length=100, required=False)
    last_name = forms.CharField(max_length=100, required=False)
    phone = forms.CharField(max_length=30, required=False)
    company = forms.CharField(max_length=200, required=False)
    source = forms.ChoiceField(choices=[
        ('order', 'Order'),
        ('signup', 'Signup'),
        ('lead_form', 'Lead form'),
        ('newsletter', 'Newsletter'),
        ('import', 'Import'),
        ('manual', 'Manual entry'),
        ('agent', 'Agent-captured'),
        ('referral', 'Referral'),
        ('other', 'Other'),
    ], required=False, initial='manual')
    accepts_marketing = forms.BooleanField(required=False)
    is_verified = forms.BooleanField(required=False)
    notes = forms.CharField(widget=forms.Textarea, required=False)

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        if instance is not None and 'initial' not in kwargs:
            kwargs['initial'] = {
                'email': instance.email,
                'first_name': instance.first_name,
                'last_name': instance.last_name,
                'phone': instance.phone,
                'company': getattr(instance, 'company', '') or '',
                'source': getattr(instance, 'source', '') or 'other',
                'accepts_marketing': instance.accepts_marketing,
                'is_verified': instance.is_verified,
                'notes': instance.notes,
            }
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        from django.contrib.auth import get_user_model
        User = get_user_model()
        qs = User.objects.filter(email__iexact=email)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A customer with this email already exists.')
        return email

    def save(self) -> Any:
        from django.contrib.auth import get_user_model
        User = get_user_model()

        cd = self.cleaned_data
        customer = self.instance or User()
        customer.email = cd['email']
        # Username is required by AbstractUser but we run email-first auth.
        if not customer.username:
            customer.username = cd['email']
        customer.first_name = cd.get('first_name') or ''
        customer.last_name = cd.get('last_name') or ''
        customer.phone = cd.get('phone') or ''
        if hasattr(customer, 'company'):
            customer.company = cd.get('company') or ''
        if hasattr(customer, 'source'):
            customer.source = cd.get('source') or 'manual'
        customer.accepts_marketing = bool(cd.get('accepts_marketing'))
        customer.is_verified = bool(cd.get('is_verified'))
        customer.notes = cd.get('notes') or ''
        if self.instance is None:
            # New customers default to unusable password — they must reset.
            customer.set_unusable_password()
            customer.is_active = True
        customer.save()
        return customer


# ── Customer address ─────────────────────────────────────────────────────────


class AddressForm(forms.Form):
    """Create/edit a `customers.Address` belonging to a given customer."""

    address_type = forms.ChoiceField(choices=[
        ('shipping', 'Shipping'),
        ('billing', 'Billing'),
    ], initial='shipping')
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    company = forms.CharField(max_length=200, required=False)
    address_line1 = forms.CharField(max_length=255)
    address_line2 = forms.CharField(max_length=255, required=False)
    city = forms.CharField(max_length=100)
    state = forms.CharField(max_length=100)
    postal_code = forms.CharField(max_length=20)
    country = forms.CharField(max_length=2, initial='US')
    phone = forms.CharField(max_length=30, required=False)
    is_default = forms.BooleanField(required=False)

    def __init__(self, *args, instance=None, customer=None, **kwargs):
        self.instance = instance
        self.customer = customer or (instance.customer if instance else None)
        if instance is not None and 'initial' not in kwargs:
            kwargs['initial'] = {
                'address_type': instance.address_type,
                'first_name': instance.first_name,
                'last_name': instance.last_name,
                'company': instance.company,
                'address_line1': instance.address_line1,
                'address_line2': instance.address_line2,
                'city': instance.city,
                'state': instance.state,
                'postal_code': instance.postal_code,
                'country': instance.country,
                'phone': instance.phone,
                'is_default': instance.is_default,
            }
        super().__init__(*args, **kwargs)

    def save(self) -> Any:
        from plugins.installed.customers.models import Address
        if self.customer is None:
            raise ValueError('AddressForm.save() requires a customer.')

        cd = self.cleaned_data
        address = self.instance or Address(customer=self.customer)
        for field in (
            'address_type', 'first_name', 'last_name', 'company',
            'address_line1', 'address_line2', 'city', 'state',
            'postal_code', 'country', 'phone',
        ):
            setattr(address, field, cd.get(field) or '')
        address.is_default = bool(cd.get('is_default'))
        address.save()
        return address


# ── Order refund ─────────────────────────────────────────────────────────────


class RefundForm(forms.Form):
    """Issue a refund against an existing order."""

    amount = forms.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    reason = forms.ChoiceField(choices=[
        ('customer_request', 'Customer request'),
        ('defective', 'Defective product'),
        ('not_as_described', 'Not as described'),
        ('wrong_item', 'Wrong item sent'),
        ('other', 'Other'),
    ], initial='customer_request')
    notes = forms.CharField(widget=forms.Textarea, required=False)

    def __init__(self, *args, order=None, **kwargs):
        self.order = order
        super().__init__(*args, **kwargs)

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if self.order is not None:
            order_total = Decimal(str(self.order.total.amount))
            already_refunded = sum(
                (Decimal(str(r.amount.amount)) for r in self.order.refunds.all()),
                Decimal('0'),
            )
            if amount + already_refunded > order_total:
                raise forms.ValidationError(
                    f'Refund total would exceed order total ({order_total}).'
                )
        return amount

    def save(self) -> Any:
        from plugins.installed.orders.models import Refund
        if self.order is None:
            raise ValueError('RefundForm.save() requires an order.')

        currency = str(getattr(self.order.total, 'currency', 'USD'))
        refund = Refund.objects.create(
            order=self.order,
            amount=_money(self.cleaned_data['amount'], currency),
            reason=self.cleaned_data['reason'],
            notes=self.cleaned_data.get('notes') or '',
            is_processed=False,
        )
        self.order.log_event(
            'REFUND_CREATED',
            message=f'{refund.amount} — {refund.get_reason_display()}',
        )
        # Ask the payments plugin (or any other listener) to issue the
        # actual refund via the gateway. Failures are logged on the order
        # timeline; the local Refund record stays in place either way.
        try:
            from morpheus import hooks
            hooks.fire('refund.requested', refund=refund)
        except Exception:  # noqa: BLE001 — never block the dashboard save
            pass
        return refund


# ── Fulfillment ──────────────────────────────────────────────────────────────


class FulfillmentForm(forms.Form):
    """Create a `Fulfillment` row covering the entire order's items.

    A line-by-line partial-fulfillment editor would be the next step up;
    today's form ships the whole order in one Fulfillment record so staff
    can record tracking + carrier without leaving the dashboard.
    """

    status = forms.ChoiceField(choices=[
        ('pending', 'Pending'),
        ('in_transit', 'In transit'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('returned', 'Returned'),
    ], initial='in_transit')
    tracking_number = forms.CharField(max_length=200, required=False)
    tracking_url = forms.URLField(required=False)
    carrier = forms.CharField(max_length=100, required=False)
    notes = forms.CharField(widget=forms.Textarea, required=False)
    mark_shipped = forms.BooleanField(
        required=False, initial=True,
        help_text="Also transition the order to 'shipped'.",
    )

    def __init__(self, *args, order=None, **kwargs):
        self.order = order
        super().__init__(*args, **kwargs)

    def save(self):
        from django.utils import timezone
        from plugins.installed.orders.models import Fulfillment, FulfillmentItem
        if self.order is None:
            raise ValueError('FulfillmentForm.save() requires an order.')
        cd = self.cleaned_data
        f = Fulfillment.objects.create(
            order=self.order,
            status=cd['status'],
            tracking_number=cd.get('tracking_number') or '',
            tracking_url=cd.get('tracking_url') or '',
            carrier=cd.get('carrier') or '',
            notes=cd.get('notes') or '',
            shipped_at=timezone.now() if cd['status'] != 'pending' else None,
        )
        # Mirror every order item into the fulfillment so reports match.
        for item in self.order.items.all():
            remaining = max(item.quantity - item.fulfilled_quantity, 0)
            if remaining <= 0:
                continue
            FulfillmentItem.objects.create(
                fulfillment=f, order_item=item, quantity=remaining,
            )
            item.fulfilled_quantity = item.quantity
            item.save(update_fields=['fulfilled_quantity'])
        return f


# ── Product variant ──────────────────────────────────────────────────────────


class VariantForm(forms.Form):
    """Create/edit a `catalog.ProductVariant` for a given product."""

    name = forms.CharField(max_length=200)
    sku = forms.CharField(max_length=100)
    price = forms.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False,
    )
    compare_at_price = forms.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False,
    )
    cost_price = forms.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False,
    )
    weight = forms.DecimalField(
        max_digits=8, decimal_places=3, required=False, min_value=Decimal('0'),
    )
    is_active = forms.BooleanField(required=False, initial=True)
    sort_order = forms.IntegerField(required=False, min_value=0, initial=0)

    def __init__(self, *args, instance=None, product=None, **kwargs):
        self.instance = instance
        self.product = product or (instance.product if instance else None)
        if instance is not None and 'initial' not in kwargs:
            kwargs['initial'] = {
                'name': instance.name,
                'sku': instance.sku,
                'price': instance.price.amount if instance.price else None,
                'compare_at_price': (
                    instance.compare_at_price.amount if instance.compare_at_price else None
                ),
                'cost_price': (
                    instance.cost_price.amount if instance.cost_price else None
                ),
                'weight': instance.weight,
                'is_active': instance.is_active,
                'sort_order': instance.sort_order,
            }
        super().__init__(*args, **kwargs)

    def clean_sku(self):
        sku = self.cleaned_data['sku'].strip()
        from plugins.installed.catalog.models import ProductVariant
        qs = ProductVariant.objects.filter(sku=sku)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Another variant already uses this SKU.')
        return sku

    def save(self) -> Any:
        from plugins.installed.catalog.models import ProductVariant
        if self.product is None:
            raise ValueError('VariantForm.save() requires a product.')

        cd = self.cleaned_data
        variant = self.instance or ProductVariant(product=self.product)
        variant.name = cd['name']
        variant.sku = cd['sku']
        variant.price = _money(cd.get('price'))
        variant.compare_at_price = _money(cd.get('compare_at_price'))
        variant.cost_price = _money(cd.get('cost_price'))
        variant.weight = cd.get('weight')
        variant.is_active = bool(cd.get('is_active'))
        variant.sort_order = cd.get('sort_order') or 0
        variant.save()
        return variant


# ── Store settings (core) ────────────────────────────────────────────────────


class StoreGeneralForm(forms.Form):
    """Editable subset of `core.StoreSettings` shown under Settings → General."""

    store_name = forms.CharField(max_length=200)
    store_description = forms.CharField(widget=forms.Textarea, required=False)
    primary_currency = forms.CharField(max_length=3)
    country = forms.CharField(max_length=2)
    timezone = forms.CharField(max_length=50, required=False)
    contact_email = forms.EmailField(required=False)
    support_phone = forms.CharField(max_length=30, required=False)

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        if instance is not None and 'initial' not in kwargs:
            kwargs['initial'] = {
                f: getattr(instance, f, '')
                for f in (
                    'store_name', 'store_description', 'primary_currency',
                    'country', 'timezone', 'contact_email', 'support_phone',
                )
            }
        super().__init__(*args, **kwargs)

    def save(self):
        from core.models import StoreSettings
        instance = self.instance or StoreSettings.objects.first() or StoreSettings()
        for field, value in self.cleaned_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance


class StoreNotificationsForm(forms.Form):
    """SMTP / outbound email — under Settings → Notifications."""

    default_from_email = forms.CharField(max_length=200, required=False)
    smtp_host = forms.CharField(max_length=200, required=False)
    smtp_port = forms.IntegerField(min_value=1, required=False, initial=587)
    smtp_user = forms.CharField(max_length=200, required=False)
    smtp_password = forms.CharField(max_length=200, required=False, widget=forms.PasswordInput(render_value=True))

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        if instance is not None and 'initial' not in kwargs:
            kwargs['initial'] = {
                f: getattr(instance, f, '')
                for f in ('default_from_email', 'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password')
            }
        super().__init__(*args, **kwargs)

    def save(self):
        from core.models import StoreSettings
        instance = self.instance or StoreSettings.objects.first() or StoreSettings()
        for field, value in self.cleaned_data.items():
            if field == 'smtp_port' and value is None:
                continue
            setattr(instance, field, value)
        instance.save()
        return instance


# ── Coupon ───────────────────────────────────────────────────────────────────


class CouponForm(forms.Form):
    """Create/edit a `marketing.Coupon`."""

    code = forms.CharField(max_length=50)
    name = forms.CharField(max_length=200)
    description = forms.CharField(widget=forms.Textarea, required=False)
    discount_type = forms.ChoiceField(choices=[
        ('percentage', 'Percentage'),
        ('fixed_amount', 'Fixed amount'),
        ('free_shipping', 'Free shipping'),
        ('buy_x_get_y', 'Buy X get Y'),
    ])
    discount_value = forms.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    minimum_order_amount = forms.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False,
    )
    maximum_discount_amount = forms.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False,
    )
    usage_limit = forms.IntegerField(min_value=0, required=False)
    usage_limit_per_customer = forms.IntegerField(min_value=0, required=False)
    is_active = forms.BooleanField(required=False, initial=True)
    starts_at = forms.DateTimeField(required=False)
    expires_at = forms.DateTimeField(required=False)

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
                    instance.maximum_discount_amount.amount if instance.maximum_discount_amount else None
                ),
                'usage_limit': instance.usage_limit,
                'usage_limit_per_customer': instance.usage_limit_per_customer,
                'is_active': instance.is_active,
                'starts_at': instance.starts_at,
                'expires_at': instance.expires_at,
            }
        super().__init__(*args, **kwargs)

    def clean_code(self):
        code = self.cleaned_data['code'].strip().upper()
        if not code:
            raise forms.ValidationError('Code is required.')
        from plugins.installed.marketing.models import Coupon
        qs = Coupon.objects.filter(code=code)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Another coupon already uses this code.')
        return code

    def save(self) -> Any:
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
        coupon.save()
        return coupon


# ── Draft order ──────────────────────────────────────────────────────────────


class DraftOrderForm(forms.Form):
    """Bare-minimum draft order: pick a customer (or just an email) + a note.

    Lines are added on the draft detail page. Once lines exist staff can
    convert the draft to a real `orders.Order` via the existing flow.
    """

    customer = forms.UUIDField(required=False)
    customer_email = forms.EmailField(required=False)
    note = forms.CharField(widget=forms.Textarea, required=False)

    def clean(self):
        cd = super().clean()
        if not cd.get('customer') and not cd.get('customer_email'):
            raise forms.ValidationError(
                'Select an existing customer or enter an email for a guest draft.'
            )
        return cd

    def save(self) -> Any:
        from plugins.installed.draft_orders.models import DraftOrder
        from django.contrib.auth import get_user_model
        User = get_user_model()

        cd = self.cleaned_data
        customer = None
        if cd.get('customer'):
            customer = User.objects.filter(pk=cd['customer']).first()

        draft = DraftOrder.objects.create(
            customer=customer,
            customer_email=(
                cd.get('customer_email') or (customer.email if customer else '')
            ),
            note=cd.get('note') or '',
        )
        return draft

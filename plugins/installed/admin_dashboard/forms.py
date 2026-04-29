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

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        if instance is not None and 'initial' not in kwargs:
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
                'short_description': instance.short_description,
                'description': instance.description,
                'category': instance.category_id,
                'vendor': instance.vendor_id,
                'is_featured': instance.is_featured,
                'is_taxable': instance.is_taxable,
                'track_inventory': instance.track_inventory,
                'requires_shipping': instance.requires_shipping,
                'weight': instance.weight,
                'weight_unit': instance.weight_unit,
            }
        super().__init__(*args, **kwargs)

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

        if cd.get('category'):
            product.category = Category.objects.filter(pk=cd['category']).first()
        else:
            product.category = None
        if cd.get('vendor'):
            product.vendor = Vendor.objects.filter(pk=cd['vendor']).first()
        else:
            product.vendor = None

        if not product.slug:
            product.slug = slugify(product.name)[:300] or 'product'
        product.save()
        return product


# ── Customer ─────────────────────────────────────────────────────────────────


class CustomerForm(forms.Form):
    """Create/edit a `customers.Customer`."""

    email = forms.EmailField()
    first_name = forms.CharField(max_length=100, required=False)
    last_name = forms.CharField(max_length=100, required=False)
    phone = forms.CharField(max_length=30, required=False)
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

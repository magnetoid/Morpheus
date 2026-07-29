"""Storefront-side vendor flows.

Views:
  - `apply`              /vendor/apply/                         — submit application.
  - `dashboard`          /vendor/me/                            — overview + KPIs.
  - `vendor_products`    /vendor/me/products/                   — catalogue list.
  - `vendor_product_edit`/vendor/me/products/<id>/              — edit one product.
  - `vendor_order_detail`/vendor/me/orders/<vendor_order_id>/   — update status + tracking.
  - `vendor_payouts`     /vendor/me/payouts/                    — accrued balance + request payout.
  - `vendor_settings`    /vendor/me/settings/                   — vendor profile + payout method.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from djmoney.money import Money

from morpheus.plugin.views import HttpRequest, HttpResponse
from plugins.installed.catalog.models import Product, Vendor
from plugins.installed.marketplace import services
from plugins.installed.marketplace.models import (
    VendorApplication,
    VendorOrder,
    VendorPayout,
    VendorPayoutAccount,
)
from plugins.registry import plugin_registry


@login_required(login_url='/auth/login/')
@require_http_methods(['GET', 'POST'])
def apply(request: HttpRequest) -> HttpResponse:
    """Vendor application form. Creates a `submitted` VendorApplication."""
    existing = VendorApplication.objects.filter(user=request.user).order_by('-submitted_at').first()

    if request.method == 'POST' and (existing is None or existing.status == 'rejected'):
        business_name = (request.POST.get('business_name') or '').strip()[:200]
        contact_email = (request.POST.get('contact_email') or request.user.email).strip()[:254]
        description = (request.POST.get('description') or '').strip()[:5000]
        tax_id = (request.POST.get('tax_id') or '').strip()[:50]
        payout_method = (request.POST.get('payout_method') or '').strip()[:40]

        if not business_name:
            return render(
                request,
                'marketplace/vendor_apply.html',
                {
                    'error': 'Business name is required.',
                    'existing': existing,
                    'seo_title': 'Sell with us',
                },
            )

        VendorApplication.objects.create(
            user=request.user,
            business_name=business_name,
            contact_email=contact_email,
            description=description,
            tax_id=tax_id,
            payout_method=payout_method,
        )
        return redirect('/vendor/me/')

    return render(
        request,
        'marketplace/vendor_apply.html',
        {
            'existing': existing,
            'seo_title': 'Sell with us',
            'seo_description': 'Apply to become a vendor on dot books. Reach our readership.',
        },
    )


@login_required(login_url='/auth/login/')
def dashboard(request: HttpRequest) -> HttpResponse:
    """Vendor dashboard for the signed-in customer."""
    application = (
        VendorApplication.objects.filter(user=request.user).order_by('-submitted_at').first()
    )

    # If this customer is also a real catalog.Vendor (i.e. their app was
    # approved + linked), surface orders + accrued payout balance.
    vendor = None
    vendor_orders: list = []
    accrued = '0.00'
    payouts: list = []
    open_orders_count = 0
    active_products_count = 0
    month_sales = '0.00'
    if application and application.status == 'approved':
        # Use the canonical link: catalog.Vendor.owner is an FK to
        # Customer, and the applicant IS a Customer. No fragile email/
        # name guessing needed.
        vendor = Vendor.objects.filter(owner=application.user).first()
        if vendor:
            vendor_orders = list(
                VendorOrder.objects.select_related('parent_order', 'vendor')
                .filter(vendor=vendor)
                .order_by('-created_at')[:25]
            )
            try:
                acct = VendorPayoutAccount.objects.get(vendor=vendor)
                accrued = str(acct.accrued_balance)
            except VendorPayoutAccount.DoesNotExist:
                pass
            payouts = list(
                VendorPayout.objects.filter(vendor=vendor).order_by('-requested_at')[:10]
            )
            open_orders_count = VendorOrder.objects.filter(
                vendor=vendor,
                status__in=['pending', 'confirmed', 'shipped'],
            ).count()
            active_products_count = Product.objects.filter(
                vendor=vendor,
                status='active',
            ).count()
            now = timezone.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            month_total = Decimal('0')
            month_qs = VendorOrder.objects.filter(
                vendor=vendor,
                created_at__gte=month_start,
            ).values_list('gross', flat=True)
            for amt in month_qs:
                month_total += amt.amount if hasattr(amt, 'amount') else Decimal(amt or 0)
            month_sales = str(month_total.quantize(Decimal('0.01')))

    return render(
        request,
        'marketplace/vendor_dashboard.html',
        {
            'application': application,
            'vendor': vendor,
            'vendor_orders': vendor_orders,
            'accrued': accrued,
            'payouts': payouts,
            'open_orders_count': open_orders_count,
            'active_products_count': active_products_count,
            'month_sales': month_sales,
            'seo_title': 'Vendor dashboard',
        },
    )


def _resolve_vendor(user):
    """Return the catalog.Vendor row owned by `user`, or None.

    Used by every self-service view to gate access — vendors can only
    see/edit their own data. The link is via catalog.Vendor.owner
    (FK to Customer), which the admin `applications_list` view sets
    when approving an application.
    """
    return Vendor.objects.filter(owner=user, is_active=True).first()


@login_required(login_url='/auth/login/')
def vendor_products(request: HttpRequest) -> HttpResponse:
    """List the signed-in vendor's products. Approved vendors only."""
    vendor = _resolve_vendor(request.user)
    if vendor is None:
        return render(
            request,
            'marketplace/vendor_products.html',
            {
                'vendor': None,
                'products': [],
                'seo_title': 'Your products',
            },
        )

    products = list(Product.objects.filter(vendor=vendor).order_by('-updated_at')[:200])
    return render(
        request,
        'marketplace/vendor_products.html',
        {
            'vendor': vendor,
            'products': products,
            'seo_title': 'Your products',
        },
    )


@login_required(login_url='/auth/login/')
@require_http_methods(['GET', 'POST'])
def vendor_product_edit(request: HttpRequest, product_id) -> HttpResponse:
    """Edit one of the signed-in vendor's products. The product must
    belong to the resolved vendor — we don't trust the URL; we double-
    check ownership server-side.

    Minimal field set (name / short / long / price / status). Vendors
    don't get to set vendor_id (they ARE the vendor), digital_file
    (security boundary), or featured (the platform's choice).
    """
    vendor = _resolve_vendor(request.user)
    if vendor is None:
        return HttpResponse(status=403, content='Not an approved vendor.')

    product = Product.objects.filter(pk=product_id, vendor=vendor).first()
    if product is None:
        return HttpResponse(status=404, content='Product not found.')

    error = ''
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()[:300]
        short = (request.POST.get('short_description') or '').strip()
        long_desc = (request.POST.get('description') or '').strip()
        status = (request.POST.get('status') or '').strip()
        raw_price = (request.POST.get('price') or '').strip()

        if not name:
            error = 'A name is required.'
        if status not in ('draft', 'active', 'archived'):
            status = product.status

        if not error and raw_price:
            try:
                amt = Decimal(raw_price)
                if amt < 0:
                    raise InvalidOperation()
                currency = product.price.currency if product.price else 'USD'
                product.price = Money(amt, currency)
            except (InvalidOperation, TypeError):
                error = 'Price must be a non-negative number.'

        if not error:
            product.name = name
            product.short_description = short
            product.description = long_desc
            product.status = status
            product.save(
                update_fields=[
                    'name',
                    'short_description',
                    'description',
                    'status',
                    'price',
                    'price_currency',
                    'updated_at',
                ]
            )
            return redirect('marketplace:vendor_products')

    return render(
        request,
        'marketplace/vendor_product_edit.html',
        {
            'vendor': vendor,
            'product': product,
            'error': error,
            'seo_title': f'Edit {product.name}',
        },
    )


# --------------------------------------------------------------------------
# Vendor self-service: order detail + tracking
# --------------------------------------------------------------------------


@login_required(login_url='/auth/login/')
@require_http_methods(['GET', 'POST'])
def vendor_order_detail(request: HttpRequest, vendor_order_id) -> HttpResponse:
    """Per-vendor order detail. Update status + tracking from one screen."""
    vendor = _resolve_vendor(request.user)
    if vendor is None:
        return HttpResponse(status=404, content='Not found.')

    vendor_order = (
        VendorOrder.objects.select_related('parent_order', 'vendor')
        .filter(pk=vendor_order_id, vendor=vendor)
        .first()
    )
    if vendor_order is None:
        return HttpResponse(status=404, content='Not found.')

    allowed_statuses = {key for key, _ in VendorOrder.STATUS_CHOICES}
    # The form exposes a narrower workflow vocabulary than the model
    # supports: preparing/packed/shipped/delivered/cancelled. Map them to
    # the model's existing CharField choices (we don't expand STATUS_CHOICES
    # — that's a wider refactor).
    form_to_model = {
        'preparing': 'confirmed',
        'packed': 'confirmed',
        'shipped': 'shipped',
        'delivered': 'delivered',
        'cancelled': 'cancelled',
    }

    if request.method == 'POST':
        raw_status = (request.POST.get('status') or '').strip().lower()
        mapped = form_to_model.get(raw_status, raw_status)
        if mapped not in allowed_statuses:
            messages.error(request, 'Unknown status.')
            return redirect('marketplace:vendor_order_detail', vendor_order_id=vendor_order.pk)

        tracking_number = (request.POST.get('tracking_number') or '').strip()[:200]
        tracking_url = (request.POST.get('tracking_url') or '').strip()[:500]

        vendor_order.status = mapped
        vendor_order.tracking_number = tracking_number
        vendor_order.tracking_url = tracking_url
        if mapped in ('shipped', 'delivered') and vendor_order.fulfilled_at is None:
            vendor_order.fulfilled_at = timezone.now()
        vendor_order.save(
            update_fields=[
                'status',
                'tracking_number',
                'tracking_url',
                'fulfilled_at',
                'updated_at',
            ]
        )
        messages.success(request, 'Order updated.')
        return redirect('marketplace:vendor_order_detail', vendor_order_id=vendor_order.pk)

    parent = vendor_order.parent_order
    shipping_address = parent.shipping_address or {}

    return render(
        request,
        'marketplace/vendor_order_detail.html',
        {
            'vendor': vendor,
            'vendor_order': vendor_order,
            'parent_order_number': parent.order_number,
            'shipping_address': shipping_address,
            'items': vendor_order.items_snapshot or [],
            'workflow_statuses': [
                ('preparing', 'Preparing'),
                ('packed', 'Packed'),
                ('shipped', 'Shipped'),
                ('delivered', 'Delivered'),
                ('cancelled', 'Cancelled'),
            ],
            'seo_title': f'Vendor order {parent.order_number}',
        },
    )


# --------------------------------------------------------------------------
# Vendor self-service: payouts
# --------------------------------------------------------------------------


@login_required(login_url='/auth/login/')
@require_http_methods(['GET', 'POST'])
def vendor_payouts(request: HttpRequest) -> HttpResponse:
    """Accrued balance + request payout + history."""
    vendor = _resolve_vendor(request.user)
    if vendor is None:
        return HttpResponse(status=404, content='Not found.')

    acct, _ = VendorPayoutAccount.objects.get_or_create(
        vendor=vendor,
        defaults={'method': 'unset'},
    )
    plugin = plugin_registry.get('marketplace')
    threshold_raw = plugin.get_config_value('min_payout_threshold', 50) if plugin else 50
    try:
        threshold = Decimal(str(threshold_raw))
    except (InvalidOperation, TypeError):
        threshold = Decimal('50')

    can_request = acct.accrued_balance.amount >= threshold and acct.method not in ('', 'unset')

    if request.method == 'POST':
        if not can_request:
            if acct.method in ('', 'unset'):
                messages.error(
                    request,
                    'Set a payout method in settings before requesting a payout.',
                )
            else:
                messages.error(
                    request,
                    f'Accrued balance is below the {threshold} threshold.',
                )
            return redirect('marketplace:vendor_payouts')
        try:
            services.request_vendor_payout(
                vendor=vendor,
                amount=acct.accrued_balance,
                method=acct.method,
            )
            messages.success(request, 'Payout requested. We will process it shortly.')
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect('marketplace:vendor_payouts')

    history = list(VendorPayout.objects.filter(vendor=vendor).order_by('-requested_at')[:50])

    return render(
        request,
        'marketplace/vendor_payouts.html',
        {
            'vendor': vendor,
            'account': acct,
            'accrued': acct.accrued_balance,
            'threshold': threshold,
            'can_request': can_request,
            'history': history,
            'seo_title': 'Payouts',
        },
    )


# --------------------------------------------------------------------------
# Vendor self-service: settings
# --------------------------------------------------------------------------


@login_required(login_url='/auth/login/')
@require_http_methods(['GET', 'POST'])
def vendor_settings(request: HttpRequest) -> HttpResponse:
    """Edit vendor profile + payout account from the storefront."""
    vendor = _resolve_vendor(request.user)
    if vendor is None:
        return HttpResponse(status=404, content='Not found.')

    acct, _ = VendorPayoutAccount.objects.get_or_create(
        vendor=vendor,
        defaults={'method': 'unset'},
    )

    error = ''
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()[:200]
        description = (request.POST.get('description') or '').strip()[:5000]
        contact_email = (request.POST.get('contact_email') or '').strip()[:254]
        method = (request.POST.get('payout_method') or '').strip()[:40]
        external_account = (request.POST.get('external_account') or '').strip()[:200]

        if not name:
            error = 'Vendor name is required.'

        if not error:
            vendor.name = name
            vendor.description = description
            vendor.save(update_fields=['name', 'description'])

            # Persist the contact email on the most recent VendorApplication
            # — catalog.Vendor has no email field of its own.
            app = (
                VendorApplication.objects.filter(user=request.user)
                .order_by('-submitted_at')
                .first()
            )
            if app and contact_email:
                app.contact_email = contact_email
                app.save(update_fields=['contact_email'])

            acct.method = method or acct.method
            acct.external_account = external_account
            acct.save(update_fields=['method', 'external_account', 'updated_at'])

            messages.success(request, 'Settings saved.')
            return redirect('marketplace:vendor_settings')

    contact_email = ''
    app = VendorApplication.objects.filter(user=request.user).order_by('-submitted_at').first()
    if app:
        contact_email = app.contact_email

    return render(
        request,
        'marketplace/vendor_settings.html',
        {
            'vendor': vendor,
            'account': acct,
            'contact_email': contact_email,
            'error': error,
            'payout_methods': [
                ('stripe', 'Stripe Connect'),
                ('bank_transfer', 'Bank transfer (SEPA / wire)'),
                ('paypal', 'PayPal'),
                ('other', 'Other'),
            ],
            'seo_title': 'Vendor settings',
        },
    )

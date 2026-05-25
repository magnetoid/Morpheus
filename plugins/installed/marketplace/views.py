"""Storefront-side vendor flows.

Two views:
  - `apply`     /vendor/apply/  — signed-in customer submits a VendorApplication.
                                 A pending row is created for admin review.
  - `dashboard` /vendor/me/     — signed-in vendor sees their application status,
                                 their vendor orders, and their accrued payout.
"""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from morpheus.views import HttpRequest, HttpResponse


@login_required(login_url='/auth/login/')
@require_http_methods(['GET', 'POST'])
def apply(request: HttpRequest) -> HttpResponse:
    """Vendor application form. Creates a `submitted` VendorApplication."""
    from plugins.installed.marketplace.models import VendorApplication

    existing = VendorApplication.objects.filter(user=request.user).order_by('-submitted_at').first()

    if request.method == 'POST' and (existing is None or existing.status == 'rejected'):
        business_name = (request.POST.get('business_name') or '').strip()[:200]
        contact_email = (request.POST.get('contact_email') or request.user.email).strip()[:254]
        description = (request.POST.get('description') or '').strip()[:5000]
        tax_id = (request.POST.get('tax_id') or '').strip()[:50]
        payout_method = (request.POST.get('payout_method') or '').strip()[:40]

        if not business_name:
            return render(request, 'marketplace/vendor_apply.html', {
                'error': 'Business name is required.',
                'existing': existing,
                'seo_title': 'Sell with us',
            })

        VendorApplication.objects.create(
            user=request.user,
            business_name=business_name,
            contact_email=contact_email,
            description=description,
            tax_id=tax_id,
            payout_method=payout_method,
        )
        return redirect('/vendor/me/')

    return render(request, 'marketplace/vendor_apply.html', {
        'existing': existing,
        'seo_title': 'Sell with us',
        'seo_description': 'Apply to become a vendor on dot books. Reach our readership.',
    })


@login_required(login_url='/auth/login/')
def dashboard(request: HttpRequest) -> HttpResponse:
    """Vendor dashboard for the signed-in customer."""
    from plugins.installed.catalog.models import Vendor
    from plugins.installed.marketplace.models import (
        VendorApplication, VendorOrder, VendorPayout, VendorPayoutAccount,
    )

    application = (
        VendorApplication.objects
        .filter(user=request.user)
        .order_by('-submitted_at').first()
    )

    # If this customer is also a real catalog.Vendor (i.e. their app was
    # approved + linked), surface orders + accrued payout balance.
    vendor = None
    vendor_orders: list = []
    accrued = '0.00'
    payouts: list = []
    if application and application.status == 'approved':
        # Use the canonical link: catalog.Vendor.owner is an FK to
        # Customer, and the applicant IS a Customer. No fragile email/
        # name guessing needed. (The previous email-match was also
        # broken — catalog.Vendor has no `email` field, so the filter
        # raised FieldError silently swallowed by .first().)
        vendor = (
            Vendor.objects
            .filter(owner=application.user)
            .first()
        )
        if vendor:
            vendor_orders = list(
                VendorOrder.objects
                .select_related('parent_order', 'vendor')
                .filter(vendor=vendor)
                .order_by('-created_at')[:25]
            )
            try:
                acct = VendorPayoutAccount.objects.get(vendor=vendor)
                accrued = str(acct.accrued_balance)
            except VendorPayoutAccount.DoesNotExist:
                pass
            payouts = list(
                VendorPayout.objects
                .filter(vendor=vendor)
                .order_by('-created_at')[:10]
            )

    return render(request, 'marketplace/vendor_dashboard.html', {
        'application': application,
        'vendor': vendor,
        'vendor_orders': vendor_orders,
        'accrued': accrued,
        'payouts': payouts,
        'seo_title': 'Vendor dashboard',
    })


def _resolve_vendor(user):
    """Return the catalog.Vendor row owned by `user`, or None.

    Used by every self-service product view to gate access — vendors
    can only see/edit their own products. The link is via
    catalog.Vendor.owner (FK to Customer), which the admin
    `applications_list` view sets when approving an application.
    """
    from plugins.installed.catalog.models import Vendor
    return Vendor.objects.filter(owner=user, is_active=True).first()


@login_required(login_url='/auth/login/')
def vendor_products(request: HttpRequest) -> HttpResponse:
    """List the signed-in vendor's products. Approved vendors only."""
    from plugins.installed.catalog.models import Product

    vendor = _resolve_vendor(request.user)
    if vendor is None:
        return render(request, 'marketplace/vendor_products.html', {
            'vendor': None,
            'products': [],
            'seo_title': 'Your products',
        })

    products = list(
        Product.objects.filter(vendor=vendor)
        .order_by('-updated_at')[:200]
    )
    return render(request, 'marketplace/vendor_products.html', {
        'vendor': vendor,
        'products': products,
        'seo_title': 'Your products',
    })


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
    from decimal import Decimal, InvalidOperation
    from djmoney.money import Money
    from plugins.installed.catalog.models import Product

    vendor = _resolve_vendor(request.user)
    if vendor is None:
        return HttpResponse(status=403, content='Not an approved vendor.')

    product = (Product.objects
               .filter(pk=product_id, vendor=vendor)
               .first())
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
                currency = (product.price.currency if product.price else 'USD')
                product.price = Money(amt, currency)
            except (InvalidOperation, TypeError):
                error = 'Price must be a non-negative number.'

        if not error:
            product.name = name
            product.short_description = short
            product.description = long_desc
            product.status = status
            product.save(update_fields=[
                'name', 'short_description', 'description', 'status',
                'price', 'price_currency', 'updated_at',
            ])
            return redirect('marketplace:vendor_products')

    return render(request, 'marketplace/vendor_product_edit.html', {
        'vendor': vendor,
        'product': product,
        'error': error,
        'seo_title': f'Edit {product.name}',
    })

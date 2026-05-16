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
        # The link between Vendor and the customer who applied isn't a
        # FK on Vendor — services.py creates the Vendor with the same
        # email or business_name. Best-effort match by email.
        vendor = (
            Vendor.objects
            .filter(email=application.contact_email)
            .first()
            or Vendor.objects.filter(name=application.business_name).first()
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

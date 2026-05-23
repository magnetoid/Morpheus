"""Marketplace dashboard pages (admin-only)."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.text import slugify


def _trail(*items):
    """Standard breadcrumb: Dashboard / Marketplace / <leaf>."""
    trail = [
        {'label': 'Dashboard', 'url': '/dashboard/'},
        {'label': 'Marketplace', 'url': '/dashboard/apps/marketplace/vendors/'},
    ]
    for item in items:
        trail.append(item if isinstance(item, dict) else {'label': str(item)})
    return trail


@staff_member_required
def vendors_list(request):
    from plugins.installed.catalog.models import Vendor
    from plugins.installed.marketplace.models import VendorOrder

    status_filter = (request.GET.get('status') or '').strip()
    qs = Vendor.objects.all().order_by('-created_at')
    if status_filter == 'active':
        qs = qs.filter(is_active=True)
    elif status_filter == 'inactive':
        qs = qs.filter(is_active=False)

    # Roll up GMV per vendor (sum of vendor_order gross).
    gross_by_vendor = dict(
        VendorOrder.objects.values_list('vendor').annotate(total=Sum('gross'))
        .values_list('vendor', 'total')
    )

    vendors = []
    for v in qs[:200]:
        vendors.append({
            'obj': v,
            'gross': gross_by_vendor.get(v.id, 0),
        })
    return render(request, 'marketplace/dashboard/vendors_list.html', {
        'vendors': vendors,
        'status_filter': status_filter,
        'active_nav': 'marketplace',
        'breadcrumb_trail': _trail({'label': 'Vendors'}),
    })


@staff_member_required
def applications_list(request):
    """Approve / reject incoming vendor applications. On approval,
    materialise a catalog.Vendor row and link it back via vendor_fk
    style (we use Vendor.owner = application.user as the canonical link).
    """
    from plugins.installed.catalog.models import Vendor
    from plugins.installed.marketplace.models import VendorApplication

    if request.method == 'POST':
        app_id = request.POST.get('application_id', '')
        action = request.POST.get('action', '')
        if app_id and action in ('approve', 'reject', 'review'):
            try:
                app = VendorApplication.objects.get(pk=app_id)
                if action == 'approve':
                    app.status = 'approved'
                    app.decided_at = timezone.now()
                    # Materialise the catalog.Vendor if not yet present.
                    existing = Vendor.objects.filter(owner=app.user).first()
                    if existing is None:
                        Vendor.objects.create(
                            name=app.business_name,
                            slug=slugify(app.business_name)[:200] or f'vendor-{app.pk.hex[:8]}',
                            description=app.description,
                            owner=app.user,
                            is_active=True,
                        )
                elif action == 'reject':
                    app.status = 'rejected'
                    app.decided_at = timezone.now()
                else:
                    app.status = 'reviewing'
                app.save(update_fields=['status', 'decided_at'])
                messages.success(request, f'Application → {app.get_status_display()}.')
            except VendorApplication.DoesNotExist:
                messages.error(request, 'Application not found.')
        return HttpResponseRedirect(request.path)

    status_filter = (request.GET.get('status') or '').strip()
    qs = VendorApplication.objects.select_related('user')
    if status_filter:
        qs = qs.filter(status=status_filter)
    apps = list(qs.order_by('-submitted_at')[:200])

    counts = dict(
        VendorApplication.objects.values_list('status').annotate(c=Count('id'))
        .values_list('status', 'c')
    )
    return render(request, 'marketplace/dashboard/applications_list.html', {
        'applications': apps,
        'counts': counts,
        'status_filter': status_filter,
        'active_nav': 'marketplace',
        'breadcrumb_trail': _trail({'label': 'Applications'}),
    })


@staff_member_required
def vendor_orders(request):
    from plugins.installed.marketplace.models import VendorOrder

    status_filter = (request.GET.get('status') or '').strip()
    qs = VendorOrder.objects.select_related('vendor', 'parent_order')
    if status_filter:
        qs = qs.filter(status=status_filter)
    rows = list(qs.order_by('-created_at')[:200])

    counts = dict(
        VendorOrder.objects.values_list('status').annotate(c=Count('id'))
        .values_list('status', 'c')
    )
    return render(request, 'marketplace/dashboard/vendor_orders.html', {
        'orders': rows,
        'counts': counts,
        'status_filter': status_filter,
        'active_nav': 'marketplace',
        'breadcrumb_trail': _trail({'label': 'Vendor orders'}),
    })


@staff_member_required
def payouts(request):
    from plugins.installed.marketplace.models import VendorPayout

    if request.method == 'POST':
        payout_id = request.POST.get('payout_id', '')
        action = request.POST.get('action', '')
        if payout_id and action in ('mark_paid', 'mark_failed', 'mark_processing'):
            try:
                p = VendorPayout.objects.get(pk=payout_id)
                if action == 'mark_paid':
                    p.status = 'paid'
                    p.paid_at = timezone.now() if hasattr(p, 'paid_at') else None
                elif action == 'mark_failed':
                    p.status = 'failed'
                elif action == 'mark_processing':
                    p.status = 'processing'
                update_fields = ['status']
                if hasattr(p, 'paid_at') and action == 'mark_paid':
                    update_fields.append('paid_at')
                p.save(update_fields=update_fields)
                messages.success(request, f'Payout → {p.get_status_display()}.')
            except VendorPayout.DoesNotExist:
                messages.error(request, 'Payout not found.')
        return HttpResponseRedirect(request.path)

    rows = list(
        VendorPayout.objects
        .select_related('vendor')
        .order_by('-created_at')[:200]
    )
    counts = dict(
        VendorPayout.objects.values_list('status').annotate(c=Count('id'))
        .values_list('status', 'c')
    )
    return render(request, 'marketplace/dashboard/payouts.html', {
        'payouts': rows,
        'counts': counts,
        'active_nav': 'marketplace',
        'breadcrumb_trail': _trail({'label': 'Payouts'}),
    })


@staff_member_required
def payout_accounts(request):
    """Manage VendorPayoutAccount rows — how each vendor gets paid."""
    from plugins.installed.marketplace.models import VendorPayoutAccount

    if request.method == 'POST':
        acct_id = request.POST.get('account_id', '')
        action = request.POST.get('action', '')
        if acct_id and action == 'toggle':
            try:
                a = VendorPayoutAccount.objects.get(pk=acct_id)
                a.is_active = not a.is_active
                a.save(update_fields=['is_active'])
                messages.success(request, f'{a.vendor.name} payout → {"active" if a.is_active else "paused"}.')
            except VendorPayoutAccount.DoesNotExist:
                messages.error(request, 'Payout account not found.')
        return HttpResponseRedirect(request.path)

    accounts = list(
        VendorPayoutAccount.objects
        .select_related('vendor')
        .order_by('-updated_at')[:200]
    )
    return render(request, 'marketplace/dashboard/payout_accounts.html', {
        'accounts': accounts,
        'active_nav': 'marketplace',
        'breadcrumb_trail': _trail({'label': 'Payout accounts'}),
    })


@staff_member_required
def reports(request):
    """Vendor performance — GMV per vendor + top vendors over a window."""
    from plugins.installed.catalog.models import Vendor
    from plugins.installed.marketplace.models import VendorOrder, VendorPayout

    try:
        days = max(1, min(int(request.GET.get('days') or 30), 365))
    except (TypeError, ValueError):
        days = 30
    since = timezone.now() - timedelta(days=days)

    gross_by_vendor = (
        VendorOrder.objects
        .filter(created_at__gte=since)
        .values('vendor', 'vendor__name')
        .annotate(
            gross=Sum('gross'),
            commission=Sum('commission'),
            net=Sum('net'),
            order_count=Count('id'),
        )
        .order_by('-gross')
    )
    top = [
        {
            'vendor_id': row['vendor'],
            'name': row['vendor__name'] or '—',
            'gross': row['gross'] or Decimal('0'),
            'commission': row['commission'] or Decimal('0'),
            'net': row['net'] or Decimal('0'),
            'orders': row['order_count'] or 0,
        }
        for row in gross_by_vendor[:25]
    ]

    summary = {
        'active_vendors': Vendor.objects.filter(is_active=True).count(),
        'total_vendors': Vendor.objects.count(),
        'orders_period': VendorOrder.objects.filter(created_at__gte=since).count(),
        'gross_period': VendorOrder.objects.filter(created_at__gte=since)
            .aggregate(t=Sum('gross'))['t'] or Decimal('0'),
        'commission_period': VendorOrder.objects.filter(created_at__gte=since)
            .aggregate(t=Sum('commission'))['t'] or Decimal('0'),
        'paid_period': VendorPayout.objects.filter(
            created_at__gte=since, status='paid',
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0'),
    }

    return render(request, 'marketplace/dashboard/reports.html', {
        'top': top,
        'summary': summary,
        'days': days,
        'active_nav': 'marketplace',
        'breadcrumb_trail': _trail({'label': 'Reports'}),
    })

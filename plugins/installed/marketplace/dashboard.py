"""Marketplace dashboard pages (admin-only).

Each view shapes its rows as a list of dicts {column_name: display_value}
so the shared `list.html` template can render real per-cell values
instead of stringifying the whole row (which is what the previous,
broken implementation did — every cell in every table showed the same
repr of the model instance).
"""
from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
def vendors_list(request):
    from plugins.installed.catalog.models import Vendor
    rows = [
        [v.name, v.slug, '✓' if v.is_active else '—', v.created_at.strftime('%Y-%m-%d')]
        for v in Vendor.objects.all().order_by('-created_at')[:200]
    ]
    return render(request, 'marketplace/dashboard/list.html', {
        'rows': rows, 'title': 'Vendors',
        'columns': ['Name', 'Slug', 'Active', 'Created'],
        'active_nav': 'marketplace',
    })


@staff_member_required
def vendor_orders(request):
    from plugins.installed.marketplace.models import VendorOrder
    qs = (
        VendorOrder.objects.select_related('vendor', 'parent_order')
        .all().order_by('-created_at')[:200]
    )
    rows = []
    for vo in qs:
        rows.append([
            vo.vendor.name if vo.vendor_id else '—',
            # Explicit order_number (not Order.__str__) so changes to
            # Order's repr don't silently break this dashboard.
            vo.parent_order.order_number if vo.parent_order_id else '—',
            vo.get_status_display(),
            str(vo.gross),
        ])
    return render(request, 'marketplace/dashboard/list.html', {
        'rows': rows, 'title': 'Vendor orders',
        'columns': ['Vendor', 'Order', 'Status', 'Gross'],
        'active_nav': 'marketplace',
    })


@staff_member_required
def payouts(request):
    from plugins.installed.marketplace.models import VendorPayout
    qs = (
        VendorPayout.objects.select_related('vendor')
        .all().order_by('-created_at')[:200]
    )
    rows = []
    for p in qs:
        rows.append([
            p.vendor.name if p.vendor_id else '—',
            str(p.amount),
            p.get_status_display(),
            p.created_at.strftime('%Y-%m-%d'),
        ])
    return render(request, 'marketplace/dashboard/list.html', {
        'rows': rows, 'title': 'Vendor payouts',
        'columns': ['Vendor', 'Amount', 'Status', 'Created'],
        'active_nav': 'marketplace',
    })

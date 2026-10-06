"""Zendrop dashboard: connection test, order sheets, placed/shipped bookkeeping."""

from __future__ import annotations

import logging

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from core.authz import require_capability
from morpheus.app.views import render, staff_member_required

logger = logging.getLogger('morpheus.zendrop.views')

PAGE = '/dashboard/apps/zendrop/orders/'


def _context() -> dict:
    from plugins.installed.zendrop.models import ZendropLink, ZendropOrder
    from plugins.installed.zendrop.services import mcp
    from plugins.installed.zendrop.services.orders import awaiting_orders, order_sheet

    sheets = [order_sheet(order) for order in awaiting_orders()]
    records = ZendropOrder.objects.select_related('order')
    return {
        'sheets': sheets,
        'unmapped_count': sum(1 for s in sheets for line in s['lines'] if not line['mapped']),
        'placed': list(records.filter(status='placed').order_by('-placed_at')[:100]),
        'attention': list(records.filter(status='cancelled').order_by('-updated_at')[:50]),
        'shipped': list(records.filter(status='shipped').order_by('-shipped_at')[:25]),
        'links_count': ZendropLink.objects.count(),
        'has_token': bool(mcp.access_token()),
        'connection': mcp.cached_connection(),
        'active_nav': 'orders',
    }


@staff_member_required
@require_capability('orders.read')
def dashboard(request):
    return render(request, 'zendrop/dashboard.html', _context())


@staff_member_required
@require_capability('orders.write')
@require_POST
def test_connection_view(request):
    from plugins.installed.zendrop.services import mcp

    snapshot = mcp.test_connection()
    if snapshot['ok']:
        messages.success(
            request, f'Connected to Zendrop — {len(snapshot["tools"])} tools available.'
        )
    else:
        messages.error(request, f'Zendrop connection failed: {snapshot["error"]}')
    return redirect(PAGE)


@staff_member_required
@require_capability('orders.write')
@require_POST
def mark_placed_view(request, order_number: str):
    from plugins.installed.orders.models import Order
    from plugins.installed.zendrop.services.orders import mark_placed

    order = get_object_or_404(Order, order_number=order_number)
    mark_placed(order, request.POST.get('zendrop_order_number', ''))
    messages.success(request, f'Order #{order.order_number} recorded as placed in Zendrop.')
    return redirect(PAGE)


@staff_member_required
@require_capability('orders.write')
@require_POST
def ship_order_view(request, order_number: str):
    from plugins.installed.orders.models import Order
    from plugins.installed.zendrop.services.orders import ship_order

    order = get_object_or_404(Order, order_number=order_number)
    reason = ship_order(
        order,
        request.POST.get('tracking_number', ''),
        request.POST.get('carrier', ''),
        request.POST.get('zendrop_order_number', ''),
    )
    if reason:
        messages.error(request, f'Order #{order.order_number} not shipped: {reason}.')
    else:
        messages.success(request, f'Order #{order.order_number} shipped with tracking.')
    return redirect(PAGE)


@staff_member_required
@require_capability('orders.write')
@require_POST
def import_tracking_view(request):
    from plugins.installed.zendrop.services.orders import TrackingImportError, import_tracking

    upload = request.FILES.get('csv')
    error = result = None
    if upload is None:
        error = 'Choose the tracking CSV first.'
    else:
        try:
            result = import_tracking(upload.read().decode('utf-8-sig', errors='ignore'))
            logger.info(
                'zendrop: tracking import shipped=%d skipped=%d unknown=%d',
                len(result['shipped']),
                len(result['skipped']),
                len(result['unknown']),
            )
        except TrackingImportError as exc:
            error = str(exc)
    return render(
        request, 'zendrop/dashboard.html', {**_context(), 'result': result, 'error': error}
    )

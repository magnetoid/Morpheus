"""DSers dashboard: export orders and the product mapping, import tracking."""

from __future__ import annotations

import logging

from django.utils import timezone
from django.views.decorators.http import require_POST

from core.authz import require_capability
from morpheus.app.views import HttpResponse, render, staff_member_required

logger = logging.getLogger('morpheus.dsers.views')


def _context() -> dict:
    from plugins.installed.dsers.models import OrderSync, SupplierLink
    from plugins.installed.dsers.services.export import eligible_orders, shippable

    awaiting = eligible_orders()
    mapped = set(SupplierLink.objects.values_list('product_id', flat=True))
    unmapped = {}
    for order in awaiting:
        for item in order.items.all():
            if shippable(item) and item.product_id and item.product_id not in mapped:
                unmapped[item.product_id] = item.product
    syncs = OrderSync.objects.select_related('order')
    return {
        'awaiting': awaiting,
        'unmapped_products': sorted(unmapped.values(), key=lambda p: p.name),
        'exported': list(syncs.filter(status='exported').order_by('-exported_at')[:100]),
        'attention': list(syncs.filter(status='cancelled').order_by('-updated_at')[:50]),
        'shipped': list(syncs.filter(status='shipped').order_by('-imported_at')[:25]),
        'links_count': SupplierLink.objects.count(),
        'active_nav': 'orders',
    }


@staff_member_required
@require_capability('orders.read')
def dashboard(request):
    return render(request, 'dsers/dashboard.html', _context())


def _csv_response(text: str, filename: str) -> HttpResponse:
    response = HttpResponse(text, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@staff_member_required
@require_capability('orders.write')
def export_orders_view(request):
    from plugins.installed.dsers.services.export import eligible_orders, export_orders

    orders = eligible_orders()
    text = export_orders(orders)
    logger.info('dsers: exported %d orders', len(orders))
    stamp = timezone.localdate().isoformat()
    return _csv_response(text, f'import_orders-{stamp}.csv')


@staff_member_required
@require_capability('catalog.read')
def export_products_view(request):
    from plugins.installed.dsers.services.export import export_products

    return _csv_response(export_products(), 'import_products.csv')


@staff_member_required
@require_capability('orders.write')
@require_POST
def import_tracking_view(request):
    from plugins.installed.dsers.services.tracking import TrackingImportError, import_tracking

    upload = request.FILES.get('csv')
    error = result = None
    if upload is None:
        error = 'Choose the CSV you downloaded from DSers first.'
    else:
        try:
            result = import_tracking(upload.read().decode('utf-8-sig', errors='ignore'))
            logger.info(
                'dsers: tracking import shipped=%d skipped=%d unknown=%d',
                len(result['shipped']),
                len(result['skipped']),
                len(result['unknown']),
            )
        except TrackingImportError as exc:
            error = str(exc)
    return render(request, 'dsers/dashboard.html', {**_context(), 'result': result, 'error': error})

"""Orders on their way to Zendrop and back.

Zendrop takes orders from a connected Shopify/Wix/TikTok/ClickFunnels store;
for any other platform the merchant places them in Zendrop by hand. This
module makes that fast and keeps Morpheus honest about it: an *order sheet*
with the supplier-ready address and the Zendrop product/variant ids per line,
"placed" bookkeeping (and the move to processing), and shipping with a
tracking number — by CSV or one order at a time — the platform way.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from plugins.dropshipping import (
    DEFAULT_TRACKING_URL,
    TrackingCsvError,
    normalised_address,
    parse_tracking_rows,
    ship_with_tracking,
    shippable,
    tracking_url,
)
from plugins.dropshipping import (
    eligible_orders as _eligible_orders,
)

TrackingImportError = TrackingCsvError


def _config() -> dict:
    from plugins.registry import app_registry

    plugin = app_registry.get('zendrop')
    return plugin.get_config() if plugin is not None else {}


def awaiting_orders() -> list:
    """Paid, shippable orders not yet placed in Zendrop."""
    return _eligible_orders('zendrop_order')


def order_sheet(order) -> dict:
    """Everything the merchant types into Zendrop for this order, ready to copy."""
    from plugins.installed.zendrop.models import ZendropLink

    links = {
        (link.product_id, link.variant_id): link
        for link in ZendropLink.objects.filter(
            product_id__in=[i.product_id for i in order.items.all()]
        )
    }
    lines = []
    for item in order.items.all():
        if not shippable(item):
            continue
        link = links.get((item.product_id, item.variant_id)) or links.get((item.product_id, None))
        lines.append(
            {
                'name': item.product_name,
                'variant': item.variant_name,
                'sku': item.sku,
                'quantity': item.quantity,
                'zendrop_product_id': link.zendrop_product_id if link else '',
                'zendrop_variant_id': link.zendrop_variant_id if link else '',
                'product_url': link.product_url if link else '',
                'mapped': bool(link and (link.zendrop_product_id or link.product_url)),
            }
        )
    return {'order': order, 'address': normalised_address(order), 'lines': lines}


def mark_placed(order, zendrop_order_number: str = '') -> None:
    """Record that the order was placed in Zendrop; move it to processing if configured."""
    from plugins.installed.zendrop.models import ZendropOrder

    with transaction.atomic():
        ZendropOrder.objects.update_or_create(
            order=order,
            defaults={
                'status': 'placed',
                'zendrop_order_number': (zendrop_order_number or '').strip()[:100],
                'placed_at': timezone.now(),
            },
        )
        if _config().get('mark_processing_when_placed', True) and order.status == 'confirmed':
            order.process()
            order.save()


def ship_order(order, tracking: str, carrier: str = '', zendrop_order_number: str = '') -> str:
    """Ship one order with ``tracking``. Returns '' on success, else the reason it was skipped."""
    from plugins.installed.zendrop.models import ZendropOrder

    tracking = (tracking or '').strip()
    if not tracking:
        return 'no tracking number'
    if order.status in ('shipped', 'delivered'):
        return 'already shipped'
    if order.status == 'cancelled':
        return 'cancelled'
    template = str(_config().get('tracking_url_template') or DEFAULT_TRACKING_URL)
    with transaction.atomic():
        ship_with_tracking(order, tracking, carrier=carrier, url=tracking_url(template, tracking))
        record, _ = ZendropOrder.objects.get_or_create(order=order, defaults={'status': 'placed'})
        record.status = 'shipped'
        record.tracking_number = tracking
        record.carrier = carrier[:100]
        record.shipped_at = timezone.now()
        if zendrop_order_number:
            record.zendrop_order_number = zendrop_order_number[:100]
        record.save()
    return ''


def import_tracking(text: str) -> dict:
    """Ship every order a tracking CSV names. Returns shipped / skipped / unknown."""
    from plugins.installed.orders.models import Order

    result: dict = {'shipped': [], 'skipped': [], 'unknown': []}
    for row in parse_tracking_rows(text):
        order = Order.objects.filter(order_number=row['order_number']).first()
        if order is None:
            result['unknown'].append(row['order_number'])
            continue
        reason = ship_order(order, row['tracking'], row['carrier'], row['supplier_order_number'])
        if reason:
            result['skipped'].append((row['order_number'], reason))
        else:
            result['shipped'].append(row['order_number'])
    return result

"""Bring DSers' tracking numbers back and ship the orders the platform way.

The file a merchant downloads from DSers after ordering carries the store's
order number, the AliExpress order number, the tracking number and usually the
carrier. Reading it by meaning and shipping through ``Order.ship()`` + an
``orders.Fulfillment`` row are the shared supplier machinery in
``plugins.dropshipping``; this module adds the DSers bookkeeping.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from plugins.dropshipping import (
    DEFAULT_TRACKING_URL,
    TrackingCsvError,
    parse_tracking_rows,
    ship_with_tracking,
    tracking_url,
)

TrackingImportError = TrackingCsvError


def _config() -> dict:
    from plugins.registry import app_registry

    plugin = app_registry.get('dsers')
    return plugin.get_config() if plugin is not None else {}


def import_tracking(text: str) -> dict:
    """Ship every order the CSV names. Returns shipped / skipped / unknown."""
    from plugins.installed.orders.models import Order

    rows = parse_tracking_rows(text)
    template = str(_config().get('tracking_url_template') or DEFAULT_TRACKING_URL)

    result: dict = {'shipped': [], 'skipped': [], 'unknown': []}
    for row in rows:
        number, tracking = row['order_number'], row['tracking']
        supplier_no, carrier = row['supplier_order_number'], row['carrier']
        order = Order.objects.filter(order_number=number).first()
        if order is None:
            result['unknown'].append(number)
            continue
        if not tracking:
            _remember(order, supplier_no=supplier_no)
            result['skipped'].append((number, 'no tracking number'))
            continue
        if order.status in ('shipped', 'delivered'):
            _remember(order, supplier_no=supplier_no)
            result['skipped'].append((number, 'already shipped'))
            continue
        if order.status == 'cancelled':
            result['skipped'].append((number, 'cancelled'))
            continue
        with transaction.atomic():
            ship_with_tracking(
                order, tracking, carrier=carrier, url=tracking_url(template, tracking)
            )
            _remember(
                order, supplier_no=supplier_no, tracking=tracking, carrier=carrier, shipped=True
            )
        result['shipped'].append(number)
    return result


def _remember(
    order, *, supplier_no: str = '', tracking: str = '', carrier: str = '', shipped=False
):
    from plugins.installed.dsers.models import OrderSync

    sync, _ = OrderSync.objects.get_or_create(order=order, defaults={'status': 'exported'})
    if supplier_no:
        sync.supplier_order_number = supplier_no
    if tracking:
        sync.tracking_number = tracking
    if carrier:
        sync.carrier = carrier
    if shipped:
        sync.status = 'shipped'
        sync.imported_at = timezone.now()
    sync.save()

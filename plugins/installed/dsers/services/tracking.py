"""Bring DSers' tracking numbers back and ship the orders the platform way.

The file a merchant downloads from DSers after ordering carries the store's
order number, the AliExpress order number, the tracking number and usually the
carrier. Only an account holder sees the exact header spelling, so columns are
matched by meaning, not by name. Shipping goes through ``Order.ship()`` and an
``orders.Fulfillment`` row — the owners of that state — so the "on its way"
email, follow-ups and merchant webhooks fire exactly as for a hand-fulfilled
order, once.
"""

from __future__ import annotations

import csv
import io
import re
from urllib.parse import quote

from django.db import transaction
from django.utils import timezone

DEFAULT_TRACKING_URL = 'https://t.17track.net/en#nums={tracking}'

ORDER_KEYS = {
    'ordernumber',
    'orderno',
    'orderid',
    'order',
    'storeordernumber',
    'storeorderno',
    'shoporderno',
    'customerordernumber',
}
TRACKING_KEYS = {
    'trackingnumber',
    'trackingno',
    'tracking',
    'trackingcode',
    'logisticstrackingnumber',
    'waybillnumber',
}
SUPPLIER_KEYS = {
    'aliexpressordernumber',
    'aliexpressorderno',
    'aliexpressorderid',
    'aliordernumber',
    'aliorderno',
    'aeorderno',
    'supplierordernumber',
    'supplierorderno',
}
CARRIER_KEYS = {
    'carrier',
    'logistics',
    'logisticscompany',
    'logisticsname',
    'shippingmethod',
    'shippingcarrier',
    'courier',
}


class TrackingImportError(ValueError):
    """The file is not a tracking export we can read."""


def _norm(header: str) -> str:
    return re.sub(r'[^a-z0-9]', '', (header or '').lower())


def _config() -> dict:
    from plugins.registry import app_registry

    plugin = app_registry.get('dsers')
    return plugin.get_config() if plugin is not None else {}


def _tracking_url(template: str, tracking: str) -> str:
    if '{tracking}' in template:
        return template.replace('{tracking}', quote(tracking, safe=''))
    return template


def import_tracking(text: str) -> dict:
    """Ship every order the CSV names. Returns shipped / skipped / unknown."""
    from plugins.installed.orders.models import Order

    reader = csv.DictReader(io.StringIO(text.lstrip('﻿')))
    headers = reader.fieldnames or []

    def find(keys: set[str]) -> str | None:
        for header in headers:
            if _norm(header) in keys:
                return header
        return None

    order_col, tracking_col = find(ORDER_KEYS), find(TRACKING_KEYS)
    if not order_col or not tracking_col:
        raise TrackingImportError(
            'Need an order-number column and a tracking-number column; '
            f'found: {", ".join(headers) or "no header row"}.'
        )
    supplier_col, carrier_col = find(SUPPLIER_KEYS), find(CARRIER_KEYS)
    template = str(_config().get('tracking_url_template') or DEFAULT_TRACKING_URL)

    result: dict = {'shipped': [], 'skipped': [], 'unknown': []}
    for row in reader:
        number = (row.get(order_col) or '').strip().lstrip('#')
        if not number:
            continue
        tracking = (row.get(tracking_col) or '').strip()
        supplier_no = (row.get(supplier_col) or '').strip() if supplier_col else ''
        carrier = (row.get(carrier_col) or '').strip() if carrier_col else ''
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
            _ship(order, tracking, carrier, supplier_no, template)
        result['shipped'].append(number)
    return result


def _ship(order, tracking: str, carrier: str, supplier_no: str, template: str) -> None:
    from plugins.installed.orders.models import Fulfillment, FulfillmentItem

    fulfillment = Fulfillment.objects.create(
        order=order,
        status='in_transit',
        tracking_number=tracking,
        tracking_url=_tracking_url(template, tracking),
        carrier=carrier,
        shipped_at=timezone.now(),
    )
    for item in order.items.all():
        remaining = item.quantity - item.fulfilled_quantity
        if remaining > 0:
            FulfillmentItem.objects.create(
                fulfillment=fulfillment, order_item=item, quantity=remaining
            )
            item.fulfilled_quantity = item.quantity
            item.save(update_fields=['fulfilled_quantity'])
    # Walk the state machine to 'shipped' from wherever the order is.
    if order.status == 'pending':
        order.confirm()
    if order.status == 'confirmed':
        order.process()
    if order.status in ('processing', 'fulfilled', 'partially_fulfilled'):
        order.ship(tracking_number=tracking)
    else:
        order.tracking_number = tracking
    order.save()
    _remember(order, supplier_no=supplier_no, tracking=tracking, carrier=carrier, shipped=True)


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

"""Send paid orders to CJ, pay them, and bring the tracking back.

CJ order calls (official docs, read 2026-10-10):

* ``POST /shopping/order/createOrderV2`` — ``orderNumber`` (ours; CJ refuses a
  duplicate with 1603003), the shipping address (``shippingCountryCode`` +
  ``shippingCountry``, ``shippingProvince``, ``shippingCity``,
  ``shippingCustomerName``, ``shippingAddress`` are required),
  ``logisticName`` + ``fromCountryCode`` (required), ``products[{vid,
  quantity, storeLineItemId}]`` and ``payType``: 2 = pay from the CJ balance
  straight away, 3 = create only (the merchant pays later);
* ``PATCH /shopping/order/confirmOrder`` + ``POST /shopping/pay/payBalance``
  — pay an order created with payType 3;
* ``POST /shopping/order/getOrderDetailBatch {"orderIds"}`` (≤ 100) — status
  (CREATED, IN_CART, UNPAID, UNSHIPPED, SHIPPED, DELIVERED, CANCELLED) and
  ``trackNumber`` / ``trackingProvider`` / ``trackingUrl``;
* ``DELETE /shopping/order/deleteOrder?orderId=`` — only while CREATED or IN_CART.

Every send is idempotent: the ``CJOrder`` row is claimed under a row lock
before the call, and only a failed send is ever retried.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from plugins.installed.cjdropshipping.services.client import CJError, config, request

logger = logging.getLogger('morpheus.cjdropshipping')

PAID_STATES = {'UNSHIPPED', 'PENDING', 'PROCESSING', 'SHIPPED', 'DELIVERED'}
DELETABLE_STATES = {'CREATED', 'IN_CART'}
OPEN = ('created', 'paid')
_DONE_ORDER_STATES = {'shipped', 'delivered', 'cancelled', 'refunded'}


def _bool(key: str, default: bool) -> bool:
    value = config().get(key, default)
    return value if isinstance(value, bool) else str(value).lower() in ('1', 'true', 'on', 'yes')


def _money(value) -> Decimal | None:
    try:
        return Decimal(str(value)).quantize(Decimal('0.01')) if value not in (None, '') else None
    except InvalidOperation:
        return None


def _country_code(raw) -> str:
    from core.utils.countries import normalise_country  # noqa: PLC0415
    from plugins.dropshipping.countries import COUNTRIES  # noqa: PLC0415

    code = normalise_country(raw)
    if code:
        return code
    wanted = str(raw or '').strip().lower()
    return next((c for c, name in COUNTRIES.items() if name.lower() == wanted), '')


def lines_for(order) -> tuple[list[dict], list[str]]:
    """CJ lines for the order's shippable items, and the names of unlinked ones."""
    from plugins.dropshipping import shippable  # noqa: PLC0415
    from plugins.installed.cjdropshipping.models import CJLink  # noqa: PLC0415

    items = [i for i in order.items.all() if shippable(i)]
    product_ids = {i.product_id for i in items if i.product_id}
    links = {
        (link.product_id, link.variant_id): link
        for link in CJLink.objects.filter(product_id__in=product_ids)
    }
    lines, unmapped = [], []
    for item in items:
        link = links.get((item.product_id, item.variant_id)) or links.get((item.product_id, None))
        if link is None:
            unmapped.append(item.product_name or str(item.product_id))
            continue
        lines.append(
            {
                'vid': link.cj_variant_id,
                'quantity': int(item.quantity),
                'storeLineItemId': str(item.pk),
            }
        )
    return lines, unmapped


def orders_to_send() -> list:
    """Paid, unsent orders with at least one line linked to CJ."""
    from plugins.dropshipping import eligible_orders  # noqa: PLC0415

    return [order for order in eligible_orders('cj_order') if lines_for(order)[0]]


def _payload(order, lines: list[dict], logistic: str, pay: bool) -> dict:
    from plugins.dropshipping import normalised_address  # noqa: PLC0415

    raw = order.shipping_address if isinstance(order.shipping_address, dict) else {}
    addr = normalised_address(order)
    code = _country_code(raw.get('country') or raw.get('country_code'))
    if not code:
        raise CJError('The shipping address has no country CJ can read.')
    city = addr['city'] or addr['province']
    return {
        'orderNumber': order.order_number,
        'shippingCountryCode': code,
        'shippingCountry': addr['country'] or code,
        'shippingProvince': addr['province'] or city,
        'shippingCity': city,
        'shippingZip': addr['zip'],
        'shippingCustomerName': addr['contact'],
        'shippingAddress': addr['line1'],
        'shippingAddress2': addr['line2'],
        'shippingPhone': addr['phone'],
        'email': addr['email'],
        'logisticName': logistic,
        'fromCountryCode': (str(config().get('ship_from_country') or 'CN').strip() or 'CN').upper()[
            :2
        ],
        'payType': 2 if pay else 3,
        'products': lines,
    }


def _logistic(lines: list[dict], country_code: str, zip_code: str) -> str:
    chosen = str(config().get('logistic_name') or '').strip()
    if chosen:
        return chosen
    from plugins.installed.cjdropshipping.services.catalog import freight_options  # noqa: PLC0415

    options = freight_options(lines, country_code, zip_code)
    if not options:
        raise CJError(f'CJ offers no shipping method to {country_code} for this order.')
    return options[0]['name']


def _claim(order):
    """Lock the order's CJOrder row for a send; ``None`` when it is already handled."""
    from plugins.installed.cjdropshipping.models import CJOrder  # noqa: PLC0415

    with transaction.atomic():
        record, created = CJOrder.objects.select_for_update().get_or_create(
            order=order, defaults={'status': 'sending'}
        )
        if not created and record.status != 'failed':
            return None
        record.status, record.note = 'sending', ''
        record.save(update_fields=['status', 'note', 'updated_at'])
    return record


def _fail(record, message: str):
    record.status, record.note = 'failed', message[:2000]
    record.save(update_fields=['status', 'note', 'updated_at'])
    logger.warning('cjdropshipping: order %s not sent: %s', record.order.order_number, message)
    return record


def forward_order(order, *, pay: bool | None = None):
    """Create ``order`` in CJ (idempotent). Returns the CJOrder, or None if already sent."""
    record = _claim(order)
    if record is None:
        return None
    pay = _bool('auto_pay', False) if pay is None else pay
    lines, unmapped = lines_for(order)
    if not lines:
        return _fail(record, 'No line of this order is linked to a CJ variant.')
    try:
        raw = order.shipping_address if isinstance(order.shipping_address, dict) else {}
        code = _country_code(raw.get('country') or raw.get('country_code'))
        logistic = _logistic(lines, code, str(raw.get('postal_code') or raw.get('zip') or ''))
        data = request(
            'POST', '/shopping/order/createOrderV2', json=_payload(order, lines, logistic, pay)
        )
    except CJError as e:
        if e.code == 1603003:  # noqa: PLR2004 — CJ already has this order number
            return adopt(record)
        return _fail(record, f'{e.message} (CJ code {e.code})' if e.code else e.message)
    data = data or {}
    record.cj_order_id = str(data.get('orderId') or '')
    record.cj_status = str(data.get('orderStatus') or '')
    record.amount = _money(data.get('actualPayment') or data.get('orderAmount'))
    record.logistic_name = logistic[:100]
    record.status = 'paid' if record.cj_status in PAID_STATES else 'created'
    notes = [
        f'{r.get("code")}: {r.get("message")}' for r in data.get('interceptOrderReasons') or []
    ]
    if unmapped:
        notes.append('Not sent (no CJ link): ' + ', '.join(unmapped))
    record.note = '; '.join(notes)[:2000]
    record.sent_at = timezone.now()
    record.save()
    _mark_processing(order)
    return record


def adopt(record):
    """CJ already holds an order with our number: take its id and state."""
    try:
        data = request(
            'GET', '/shopping/order/getOrderDetail', params={'orderId': record.order.order_number}
        )
    except CJError as e:
        return _fail(record, f'CJ has this order but it could not be read: {e.message}')
    _apply_detail(record, data or {})
    return record


def _mark_processing(order) -> None:
    if not _bool('mark_processing_when_sent', True):
        return
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    with transaction.atomic():
        fresh = Order.objects.select_for_update().get(pk=order.pk)
        if fresh.status == 'confirmed':
            fresh.process()
            fresh.save()


def pay(record) -> str:
    """Pay a created order from the CJ balance; returns '' or the reason it failed."""
    try:
        try:
            request('PATCH', '/shopping/order/confirmOrder', json={'orderId': record.cj_order_id})
        except CJError as e:
            if e.code != 1603001:  # noqa: PLR2004 — already confirmed is fine
                raise
        request('POST', '/shopping/pay/payBalance', json={'orderId': record.cj_order_id})
    except CJError as e:
        record.note = f'Payment failed: {e.message}'[:2000]
        record.save(update_fields=['note', 'updated_at'])
        return e.message
    record.status, record.note = 'paid', ''
    record.save(update_fields=['status', 'note', 'updated_at'])
    return ''


def _tracking_url(tracking: str, given: str = '') -> str:
    if given:
        return given
    from plugins.dropshipping import tracking_url  # noqa: PLC0415

    return tracking_url(str(config().get('tracking_url_template') or ''), tracking)


def ship(record, tracking: str, *, carrier: str = '', url: str = '') -> None:
    """Ship the store order with CJ's tracking number, once."""
    from plugins.dropshipping import ship_with_tracking  # noqa: PLC0415
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    tracking = (tracking or '').strip()
    if not tracking or (record.status == 'shipped' and record.tracking_number == tracking):
        return
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=record.order_id)
        if order.status not in _DONE_ORDER_STATES:
            ship_with_tracking(order, tracking, carrier=carrier, url=_tracking_url(tracking, url))
        record.status = 'shipped'
        record.tracking_number = tracking[:200]
        record.carrier = (carrier or record.logistic_name)[:100]
        record.shipped_at = timezone.now()
        record.save()


def _apply_detail(record, detail: dict) -> None:
    record.cj_order_id = str(detail.get('orderId') or record.cj_order_id or '')
    record.cj_status = str(detail.get('orderStatus') or record.cj_status or '')
    if record.cj_status in PAID_STATES and record.status in ('sending', 'created', 'failed'):
        record.status = 'paid'
    elif record.status in ('sending', 'failed'):
        record.status = 'created'
    record.logistic_name = str(detail.get('logisticName') or record.logistic_name or '')[:100]
    record.save()
    tracking = str(detail.get('trackNumber') or '')
    if tracking:
        ship(
            record,
            tracking,
            carrier=str(detail.get('trackingProvider') or ''),
            url=str(detail.get('trackingUrl') or ''),
        )


def sync_open_orders() -> int:
    """Refresh every open CJ order from CJ (status, payment, tracking). Returns the count read."""
    from plugins.installed.cjdropshipping.models import CJOrder  # noqa: PLC0415

    records = {
        r.cj_order_id: r for r in CJOrder.objects.filter(status__in=OPEN).exclude(cj_order_id='')
    }
    ids = list(records)
    read = 0
    for start in range(0, len(ids), 50):
        batch = ids[start : start + 50]
        details = (
            request('POST', '/shopping/order/getOrderDetailBatch', json={'orderIds': batch}) or []
        )
        for detail in details:
            record = records.get(str(detail.get('orderId') or '')) or records.get(
                str(detail.get('cjOrderId') or '')
            )
            if record is not None:
                _apply_detail(record, detail)
                read += 1
    return read


def cancel(record) -> None:
    """The store order was cancelled: delete it at CJ while CJ still allows that."""
    if record.status in ('shipped', 'cancelled'):
        return
    note = 'Cancelled in Morpheus — open a dispute in CJ if it was already paid.'
    if record.cj_order_id and record.cj_status in DELETABLE_STATES | {''}:
        try:
            request('DELETE', '/shopping/order/deleteOrder', params={'orderId': record.cj_order_id})
            note = 'Cancelled in Morpheus and deleted in CJ.'
        except CJError as e:
            note = f'Cancelled in Morpheus; CJ refused the delete ({e.message}) — cancel it in CJ.'
    record.status, record.note = 'cancelled', note
    record.save(update_fields=['status', 'note', 'updated_at'])

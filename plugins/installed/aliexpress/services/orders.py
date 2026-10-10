"""Place paid orders on AliExpress, follow their payment and tracking.

AliExpress DS order methods (official docs, read 2026-10-10):

* ``aliexpress.ds.order.create`` — ``param_place_order_request4_open_api_d_t_o``
  (JSON): ``out_order_id`` (ours; AliExpress treats it as an idempotency key for
  24 h), ``logistics_address`` (``address``, ``city``, ``province``, ``country``
  are required; AliExpress writes the United Kingdom as "UK"), and
  ``product_items[{product_id, product_count, sku_attr, logistics_service_name}]``
  where ``logistics_service_name`` is a freight option's ``code``. Optional
  ``ds_extend_request.payment = {pay_currency: "USD", try_to_pay: "true"}`` pays
  through PayPal — only for accounts AliExpress whitelisted for it. Response
  ``result.is_success``, ``result.order_list`` (one AliExpress order per seller),
  ``result.error_code`` / ``error_msg``.
* Otherwise a DS order is paid by the merchant in the AliExpress buyer account,
  before ``pay_timeout_second`` runs out (often one day), or AliExpress closes it.
* ``aliexpress.trade.ds.order.get`` — ``single_order_query {order_id}`` →
  ``order_status`` (PLACE_ORDER_SUCCESS, PAYMENT_PROCESSING,
  WAIT_SELLER_EXAMINE_MONEY, RISK_CONTROL, WAIT_SELLER_SEND_GOODS,
  SELLER_PART_SEND_GOODS, WAIT_BUYER_ACCEPT_GOODS, FINISH, IN_CANCEL, …) and
  ``pay_timeout_second``. Query no sooner than ~10 s after creating.
* ``aliexpress.ds.order.tracking.get`` — ``ae_order_id``, ``language`` →
  ``data.tracking_detail_line_list[]`` (``mail_no``, ``carrier_name``).
* There is no cancel method: a store cancellation is flagged for the merchant.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from plugins.installed.aliexpress.services.client import AEError, call, config

logger = logging.getLogger('morpheus.aliexpress')

PAID_STATES = {
    'WAIT_SELLER_EXAMINE_MONEY',
    'RISK_CONTROL',
    'RISK_CONTROL_HOLD',
    'WAIT_SELLER_SEND_GOODS',
    'SELLER_PART_SEND_GOODS',
    'WAIT_BUYER_ACCEPT_GOODS',
    'FINISH',
}
CANCEL_STATES = {'IN_CANCEL'}
OPEN = ('placed', 'paid')
_DONE_ORDER_STATES = {'shipped', 'delivered', 'cancelled', 'refunded'}


def _bool(key: str, default: bool) -> bool:
    value = config().get(key, default)
    return value if isinstance(value, bool) else str(value).lower() in ('1', 'true', 'on', 'yes')


def _country_code(raw) -> str:
    from core.utils.countries import normalise_country  # noqa: PLC0415
    from plugins.dropshipping.countries import COUNTRIES  # noqa: PLC0415

    code = normalise_country(raw)
    if code:
        return code
    wanted = str(raw or '').strip().lower()
    return next((c for c, name in COUNTRIES.items() if name.lower() == wanted), '')


def lines_for(order) -> tuple[list[dict], list[str]]:
    """``[{link, quantity}]`` for the order's AliExpress-linked shippable items."""
    from plugins.dropshipping import shippable  # noqa: PLC0415
    from plugins.installed.aliexpress.models import AELink  # noqa: PLC0415

    items = [i for i in order.items.all() if shippable(i)]
    links = {
        (link.product_id, link.variant_id): link
        for link in AELink.objects.filter(
            product_id__in={i.product_id for i in items if i.product_id}
        )
    }
    lines, unmapped = [], []
    for item in items:
        link = links.get((item.product_id, item.variant_id)) or links.get((item.product_id, None))
        if link is None:
            unmapped.append(item.product_name or str(item.product_id))
        else:
            lines.append({'link': link, 'quantity': int(item.quantity)})
    return lines, unmapped


def orders_to_send() -> list:
    from plugins.dropshipping import eligible_orders  # noqa: PLC0415

    return [order for order in eligible_orders('ae_order') if lines_for(order)[0]]


def _service_for(line: dict, country: str) -> str:
    chosen = str(config().get('logistics_service') or '').strip()
    if chosen:
        return chosen
    from plugins.installed.aliexpress.services.catalog import freight_options  # noqa: PLC0415

    link = line['link']
    options = freight_options(link.ae_product_id, link.ae_sku_id, line['quantity'], country)
    if not options:
        raise AEError(
            f'AliExpress offers no delivery to {country} for product {link.ae_product_id}.'
        )
    return options[0]['code']


def _payload(order, lines: list[dict]) -> dict:
    from plugins.dropshipping import normalised_address  # noqa: PLC0415
    from plugins.installed.aliexpress.services.catalog import ae_country  # noqa: PLC0415

    raw = order.shipping_address if isinstance(order.shipping_address, dict) else {}
    addr = normalised_address(order)
    code = _country_code(raw.get('country') or raw.get('country_code'))
    if not code:
        raise AEError('The shipping address has no country AliExpress can read.')
    city = addr['city'] or addr['province']
    request = {
        'out_order_id': order.order_number,
        'logistics_address': {
            'address': addr['line1'],
            'address2': addr['line2'],
            'city': city,
            'province': addr['province'] or city,
            'country': ae_country(code),
            'zip': addr['zip'],
            'contact_person': addr['contact'],
            'full_name': addr['contact'],
            'mobile_no': addr['phone'].lstrip('+'),
        },
        'product_items': [
            {
                'product_id': int(line['link'].ae_product_id),
                'product_count': line['quantity'],
                'sku_attr': line['link'].sku_attr,
                'logistics_service_name': _service_for(line, code),
            }
            for line in lines
        ],
    }
    params = {'param_place_order_request4_open_api_d_t_o': request}
    if _bool('auto_pay', False):
        params['ds_extend_request'] = {'payment': {'pay_currency': 'USD', 'try_to_pay': 'true'}}
    return params


def _claim(order):
    from plugins.installed.aliexpress.models import AEOrder  # noqa: PLC0415

    with transaction.atomic():
        record, created = AEOrder.objects.select_for_update().get_or_create(
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
    logger.warning('aliexpress: order %s not placed: %s', record.order.order_number, message)
    return record


def forward_order(order):
    """Place ``order`` on AliExpress (idempotent). Returns the AEOrder, or None if already placed."""
    record = _claim(order)
    if record is None:
        return None
    lines, unmapped = lines_for(order)
    if not lines:
        return _fail(record, 'No line of this order is linked to an AliExpress product.')
    try:
        payload = call('aliexpress.ds.order.create', _payload(order, lines))
    except (AEError, ValueError) as e:
        return _fail(record, getattr(e, 'message', str(e)))
    result = payload.get('result') or {}
    ids = [str(i) for i in result.get('order_list') or [] if i]
    if str(result.get('is_success')).lower() != 'true' or not ids:
        reason = (
            result.get('error_msg')
            or result.get('error_code')
            or 'AliExpress did not place the order.'
        )
        return _fail(
            record,
            f'{reason} ({result.get("error_code")})' if result.get('error_code') else str(reason),
        )
    notes = []
    if result.get('error_msg'):
        notes.append(str(result['error_msg']))  # e.g. "OrderCreated, autoPay fail:APIPayFail"
    if unmapped:
        notes.append('Not placed (no AliExpress link): ' + ', '.join(unmapped))
    record.ae_order_ids = ids
    record.status = 'placed'
    record.note = '; '.join(notes)[:2000]
    record.sent_at = timezone.now()
    record.pay_by = record.sent_at + timedelta(days=1)  # refined from pay_timeout_second on sync
    record.save()
    _mark_processing(order)
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


def _tracking_url(tracking: str) -> str:
    from plugins.dropshipping import tracking_url  # noqa: PLC0415

    return tracking_url(str(config().get('tracking_url_template') or ''), tracking)


def ship(record) -> None:
    """Ship the store order once every AliExpress order of it has a tracking number."""
    from plugins.dropshipping import ship_with_tracking  # noqa: PLC0415
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    numbers = [record.tracking_numbers.get(i, {}).get('number', '') for i in record.ae_order_ids]
    if not numbers or not all(numbers) or record.status == 'shipped':
        return
    carriers = sorted(
        {record.tracking_numbers[i].get('carrier', '') for i in record.ae_order_ids} - {''}
    )
    tracking = ', '.join(numbers)
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=record.order_id)
        if order.status not in _DONE_ORDER_STATES:
            ship_with_tracking(
                order,
                tracking[:200],
                carrier=', '.join(carriers)[:100],
                url=_tracking_url(numbers[0]),
            )
        record.status = 'shipped'
        record.carrier = ', '.join(carriers)[:200]
        record.shipped_at = timezone.now()
        record.save()


def _order_status(ae_order_id: str) -> dict:
    payload = call(
        'aliexpress.trade.ds.order.get', {'single_order_query': {'order_id': int(ae_order_id)}}
    )
    return payload.get('result') or {}


def _tracking(ae_order_id: str) -> dict:
    payload = call(
        'aliexpress.ds.order.tracking.get', {'ae_order_id': ae_order_id, 'language': 'en_US'}
    )
    result = payload.get('result') or {}
    lines = (result.get('data') or {}).get('tracking_detail_line_list') or []
    for line in lines:
        if line.get('mail_no'):
            return {'number': str(line['mail_no']), 'carrier': str(line.get('carrier_name') or '')}
    return {}


def refresh(record) -> None:
    """Read every AliExpress order of ``record``: payment state, deadline, tracking."""
    statuses = []
    for ae_id in record.ae_order_ids:
        detail = _order_status(ae_id)
        status = str(detail.get('order_status') or '')
        statuses.append(status)
        timeout = detail.get('pay_timeout_second')
        if status == 'PLACE_ORDER_SUCCESS' and timeout not in (None, '') and record.sent_at:
            with contextlib.suppress(ValueError):
                record.pay_by = record.sent_at + timedelta(seconds=int(str(timeout)))
        if status in PAID_STATES and not record.tracking_numbers.get(ae_id, {}).get('number'):
            found = _tracking(ae_id)
            if found:
                record.tracking_numbers = {**record.tracking_numbers, ae_id: found}
    record.ae_status = ', '.join(sorted(set(statuses)))[:40]
    if any(s in CANCEL_STATES for s in statuses):
        record.note = 'AliExpress is cancelling an order of this purchase — check it in AliExpress.'
    if statuses and all(s in PAID_STATES for s in statuses) and record.status == 'placed':
        record.status = 'paid'
    record.save()
    ship(record)


def sync_open_orders() -> int:
    from plugins.installed.aliexpress.models import AEOrder  # noqa: PLC0415

    count = 0
    for record in AEOrder.objects.filter(status__in=OPEN).select_related('order')[:200]:
        try:
            refresh(record)
            count += 1
        except AEError as e:
            logger.info(
                'aliexpress: refresh of %s failed: %s', record.order.order_number, e.message
            )
    return count


def cancel(record) -> None:
    """No cancel method exists: flag the order for a cancel in the AliExpress account."""
    if record.status in ('shipped', 'cancelled'):
        return
    ids = ', '.join(record.ae_order_ids) or '—'
    record.status = 'cancelled'
    record.note = (
        f'Cancelled in Morpheus — cancel AliExpress order(s) {ids} in the AliExpress account '
        '(an unpaid one closes by itself after the payment deadline).'
    )
    record.save(update_fields=['status', 'note', 'updated_at'])

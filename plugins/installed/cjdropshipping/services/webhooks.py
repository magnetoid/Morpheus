"""CJ webhooks: register the store's URL, check the signature, apply the message.

Official contract (developers.cjdropshipping.com, webhook pages, 2026-10-10):

* ``POST /webhook/set`` with the four required topics ``product``, ``stock``,
  ``order``, ``logistics`` as ``{"type": "ENABLE"|"CANCEL", "callbackUrls":
  [one public https URL]}``. CJ first POSTs a test payload to the URL and the
  registration fails unless it answers 200 within 3 seconds.
* Every push carries the header ``sign`` = Base64(HMAC-SHA256(key = the
  account's openId as text, message = the raw body)); verify on the raw bytes,
  never on re-serialised JSON. Pushes are retried up to 3 times, and a topic is
  closed automatically when fewer than 80% succeed over two hours.
* Bodies are ``{messageId, type, messageType, params}``: ``ORDER`` (params
  ``cjOrderId``, ``orderNumber``, ``orderStatus``, ``trackNumber``,
  ``trackingProvider``, ``trackingUrl``), ``LOGISTIC`` (params ``orderId``,
  ``storeOrderNumbers[]``, ``logisticName``, ``trackingNumber``,
  ``trackingProvider``, ``trackingUrl``, ``trackingStatus``), ``STOCK`` (params:
  a map vid → [{storageNum, …}]) and ``VARIANT`` (params ``vid``,
  ``variantSellPrice``).

The view always answers 200 — the registration probe may not be signed — but
only a message whose signature verifies changes anything.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from decimal import Decimal, InvalidOperation

logger = logging.getLogger('morpheus.cjdropshipping')

TOPICS = ('product', 'stock', 'order', 'logistics')


def signature(body: bytes, open_id: str) -> str:
    digest = hmac.new(str(open_id).encode(), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def verify(body: bytes, sign: str, open_id: str) -> bool:
    if not sign or not open_id:
        return False
    return hmac.compare_digest(signature(body, open_id), sign.strip())


def register(url: str, *, enable: bool = True) -> None:
    from plugins.installed.cjdropshipping.services.client import request  # noqa: PLC0415

    state = 'ENABLE' if enable else 'CANCEL'
    request(
        'POST', '/webhook/set', json={t: {'type': state, 'callbackUrls': [url]} for t in TOPICS}
    )


def _record_for(*, cj_order_id: str = '', order_numbers=()):
    from plugins.installed.cjdropshipping.models import CJOrder  # noqa: PLC0415

    if cj_order_id:
        record = CJOrder.objects.filter(cj_order_id=cj_order_id).select_related('order').first()
        if record is not None:
            return record
    numbers = [str(n) for n in order_numbers if n]
    if numbers:
        return (
            CJOrder.objects.filter(order__order_number__in=numbers).select_related('order').first()
        )
    return None


def _first_seen(message_id: str) -> bool:
    """CJ keeps ``messageId`` across retries; apply each message once."""
    if not message_id:
        return True
    from django.core.cache import cache  # noqa: PLC0415

    return cache.add(f'cj:msg:{message_id}', 1, timeout=60 * 60 * 24)


def apply(message: dict) -> str:
    """Apply one verified message; returns what happened, for the log."""
    if not _first_seen(str(message.get('messageId') or '')):
        return 'duplicate'
    kind = str(message.get('type') or '').upper()
    params = message.get('params') if isinstance(message.get('params'), dict) else {}
    handler = _HANDLERS.get(kind)
    return handler(params) if handler else f'ignored {kind or "unknown"}'


def _apply_order(params: dict) -> str:
    from plugins.installed.cjdropshipping.services import orders  # noqa: PLC0415

    record = _record_for(
        cj_order_id=str(params.get('cjOrderId') or ''),
        order_numbers=[params.get('orderNumber'), params.get('orderNum')],
    )
    if record is None:
        return 'order not ours'
    orders._apply_detail(
        record,
        {
            'orderId': params.get('cjOrderId'),
            'orderStatus': params.get('orderStatus'),
            'logisticName': params.get('logisticName'),
            'trackNumber': params.get('trackNumber'),
            'trackingProvider': params.get('trackingProvider'),
            'trackingUrl': params.get('trackingUrl'),
        },
    )
    return 'order updated'


def _apply_logistic(params: dict) -> str:
    from plugins.installed.cjdropshipping.services import orders  # noqa: PLC0415

    record = _record_for(
        cj_order_id=str(params.get('orderId') or ''),
        order_numbers=params.get('storeOrderNumbers') or [],
    )
    if record is None:
        return 'order not ours'
    orders.ship(
        record,
        str(params.get('trackingNumber') or ''),
        carrier=str(params.get('trackingProvider') or params.get('logisticName') or ''),
        url=str(params.get('trackingUrl') or ''),
    )
    return 'tracking recorded'


def _apply_stock(params: dict) -> str:
    from plugins.installed.cjdropshipping.models import CJLink  # noqa: PLC0415

    updated = 0
    for vid, rows in params.items():
        if not isinstance(rows, list):
            continue
        total = 0
        for row in rows:
            try:
                total += int(row.get('storageNum') or row.get('totalInventoryNum') or 0)
            except (TypeError, ValueError, AttributeError):
                continue
        updated += CJLink.objects.filter(cj_variant_id=str(vid)).update(stock=total)
    return f'stock for {updated} links'


def _apply_variant(params: dict) -> str:
    from plugins.installed.cjdropshipping.models import CJLink  # noqa: PLC0415

    vid = str(params.get('vid') or '')
    if not vid or params.get('variantSellPrice') in (None, ''):
        return 'variant: nothing to apply'
    try:
        cost = Decimal(str(params['variantSellPrice'])).quantize(Decimal('0.01'))
    except InvalidOperation:
        return 'variant: unreadable price'
    count = CJLink.objects.filter(cj_variant_id=vid).update(cost=cost)
    return f'cost for {count} links'


_HANDLERS = {
    'ORDER': _apply_order,
    'LOGISTIC': _apply_logistic,
    'STOCK': _apply_stock,
    'VARIANT': _apply_variant,
}

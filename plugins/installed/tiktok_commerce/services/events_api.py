"""TikTok Events API (server-side) — iOS-safe, ad-blocker-proof conversions.

    POST /event/track/  { event_source: web, event_source_id: <pixel_code>,
                          data: [{ event, event_time, event_id, user, properties }] }

Fires CompletePayment / AddToCart / InitiateCheckout server-side with content_ids
matched to the catalog feed id; user email/phone SHA-256 hashed. CompletePayment
event_id = order_number so it dedupes against the browser Pixel. No-op when
unconfigured.
"""

from __future__ import annotations

import hashlib
import logging
import time

from plugins.capi_shared import line_items as _line_items
from plugins.capi_shared import money_tuple as _money

from .api import creds, has_token, post

logger = logging.getLogger('morpheus.tiktok_commerce')


def _sha256(value: str) -> str:
    return hashlib.sha256((value or '').strip().lower().encode('utf-8')).hexdigest()


def _send(event: str, *, value: float, currency: str, items, email='', event_id='') -> dict:
    c = creds()
    if not (has_token() and c['pixel_code']):
        return {'ok': False, 'reason': 'not_connected'}
    user = {'email': _sha256(email)} if email else {}
    payload = {
        'event_source': 'web',
        'event_source_id': c['pixel_code'],
        'data': [
            {
                'event': event,
                'event_time': int(time.time()),
                'event_id': str(event_id or ''),
                'user': user,
                'properties': {
                    'currency': currency,
                    'value': value,
                    'content_type': 'product',
                    'contents': [{'content_id': sku, 'quantity': qty} for sku, qty in items],
                },
            }
        ],
    }
    res = post('event/track/', payload)
    _log(res, event)
    return res


def send_complete_payment(order) -> dict:
    value, currency = _money(getattr(order, 'total', None))
    return _send(
        'CompletePayment',
        value=value,
        currency=currency,
        items=_line_items(order),
        email=getattr(order, 'email', '') or '',
        event_id=str(getattr(order, 'order_number', '') or getattr(order, 'pk', '')),
    )


def send_add_to_cart(*, product=None, variant=None, quantity=1) -> dict:
    target = variant or product
    sku = getattr(target, 'sku', '') or getattr(product, 'sku', '')
    if not sku:
        return {'ok': False, 'reason': 'no_sku'}
    value, currency = _money(getattr(target, 'price', None) or getattr(product, 'price', None))
    return _send(
        'AddToCart', value=value * (quantity or 1), currency=currency, items=[(sku, quantity or 1)]
    )


def send_initiate_checkout(cart) -> dict:
    value, currency = _money(getattr(cart, 'total', None) or getattr(cart, 'subtotal', None))
    return _send('InitiateCheckout', value=value, currency=currency, items=_line_items(cart))


def _log(res: dict, event: str) -> None:
    try:
        from plugins.installed.tiktok_commerce.models import TiktokSyncLog  # noqa: PLC0415

        TiktokSyncLog.objects.create(
            kind=TiktokSyncLog.KIND_EVENTS,
            status=TiktokSyncLog.STATUS_OK if res.get('ok') else TiktokSyncLog.STATUS_ERROR,
            item_count=1 if res.get('ok') else 0,
            errors=[] if res.get('ok') else [str(res.get('reason'))[:300]],
            message=f'Events API {event}',
        )
    except Exception as e:  # noqa: BLE001
        logger.debug('tiktok_commerce: events log failed: %s', e)

"""Meta Conversions API — server-side events for iOS-safe attribution.

    POST /{pixel_id}/events { data: [{event_name, event_time, user_data, ...}] }

Fires server-side Purchase events (hashed user data) so conversions are
attributed even when the browser pixel is blocked. Hooked to ORDER_PAID.
Graceful no-op when no pixel id / token. content_ids match the catalog feed id
(product SKU) so they line up with the catalog + dynamic ads.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time

from .graph import creds, has_token, post

logger = logging.getLogger('morpheus.meta_commerce')


def _sha256(value: str) -> str:
    return hashlib.sha256((value or '').strip().lower().encode('utf-8')).hexdigest()


def _line_items(order):
    """[(retailer_id, qty, price)] from an order, best-effort."""
    out = []
    for line in getattr(order, 'items', getattr(order, 'lines', None)) or []:
        sku = (
            getattr(line, 'sku', '')
            or getattr(getattr(line, 'variant', None), 'sku', '')
            or getattr(getattr(line, 'product', None), 'sku', '')
        )
        if sku:
            out.append((sku, getattr(line, 'quantity', 1)))
    return out


def _money(m) -> tuple[float, str]:
    amount = getattr(m, 'amount', None)
    return (float(amount) if amount is not None else 0.0), str(getattr(m, 'currency', '') or 'USD')


def _send(event_name: str, *, value: float, currency: str, items, email='', event_id='') -> dict:
    """Core CAPI sender. items = [(sku, qty)]. No-op when unconfigured."""
    c = creds()
    if not (has_token() and c['pixel_id']):
        return {'ok': False, 'reason': 'not_connected'}
    user_data = {'em': [_sha256(email)]} if email else {}
    event = {
        'event_name': event_name,
        'event_time': int(time.time()),
        'action_source': 'website',
        'event_id': str(event_id or ''),
        'user_data': user_data,
        'custom_data': {
            'currency': currency,
            'value': value,
            'content_type': 'product',
            'content_ids': [sku for sku, _ in items],
            'contents': [{'id': sku, 'quantity': qty} for sku, qty in items],
        },
    }
    res = post(f'{c["pixel_id"]}/events', {'data': json.dumps([event])})
    _log(res, event_name)
    return res


def send_purchase(order) -> dict:
    """Server-side Purchase event for `order`."""
    value, currency = _money(getattr(order, 'total', None))
    return _send(
        'Purchase',
        value=value,
        currency=currency,
        items=_line_items(order),
        email=getattr(order, 'email', '') or '',
        event_id=str(getattr(order, 'order_number', '') or getattr(order, 'pk', '')),
    )


def send_add_to_cart(*, product=None, variant=None, quantity=1) -> dict:
    """Server-side AddToCart — sharpens dynamic-ads/Advantage+ optimisation."""
    target = variant or product
    sku = getattr(target, 'sku', '') or getattr(product, 'sku', '')
    if not sku:
        return {'ok': False, 'reason': 'no_sku'}
    value, currency = _money(getattr(target, 'price', None) or getattr(product, 'price', None))
    return _send(
        'AddToCart',
        value=value * (quantity or 1),
        currency=currency,
        items=[(sku, quantity or 1)],
    )


def send_initiate_checkout(cart) -> dict:
    """Server-side InitiateCheckout from a cart."""
    value, currency = _money(getattr(cart, 'total', None) or getattr(cart, 'subtotal', None))
    items = []
    for line in getattr(cart, 'items', getattr(cart, 'lines', None)) or []:
        sku = (
            getattr(line, 'sku', '')
            or getattr(getattr(line, 'variant', None), 'sku', '')
            or getattr(getattr(line, 'product', None), 'sku', '')
        )
        if sku:
            items.append((sku, getattr(line, 'quantity', 1)))
    return _send('InitiateCheckout', value=value, currency=currency, items=items)


def _log(res: dict, event_name: str = 'Purchase') -> None:
    try:
        from plugins.installed.meta_commerce.models import MetaSyncLog  # noqa: PLC0415

        MetaSyncLog.objects.create(
            kind=MetaSyncLog.KIND_CAPI,
            status=MetaSyncLog.STATUS_OK if res.get('ok') else MetaSyncLog.STATUS_ERROR,
            item_count=1 if res.get('ok') else 0,
            errors=[] if res.get('ok') else [str(res.get('reason'))[:300]],
            message=f'CAPI {event_name}',
        )
    except Exception as e:  # noqa: BLE001
        logger.debug('meta_commerce: capi log failed: %s', e)

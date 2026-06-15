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


def send_purchase(order) -> dict:
    """Send a server-side Purchase event for `order`. No-op when unconfigured."""
    c = creds()
    if not (has_token() and c['pixel_id']):
        return {'ok': False, 'reason': 'not_connected'}

    total = getattr(order, 'total', None)
    amount = getattr(total, 'amount', None)
    currency = str(getattr(total, 'currency', '') or 'USD')
    email = getattr(order, 'email', '') or ''
    items = _line_items(order)

    user_data = {}
    if email:
        user_data['em'] = [_sha256(email)]

    event = {
        'event_name': 'Purchase',
        'event_time': int(time.time()),
        'action_source': 'website',
        'event_id': str(getattr(order, 'order_number', '') or getattr(order, 'pk', '')),
        'user_data': user_data,
        'custom_data': {
            'currency': currency,
            'value': float(amount) if amount is not None else 0.0,
            'content_type': 'product',
            'content_ids': [sku for sku, _ in items],
            'contents': [{'id': sku, 'quantity': qty} for sku, qty in items],
        },
    }
    res = post(f'{c["pixel_id"]}/events', {'data': json.dumps([event])})
    _log(res)
    return res


def _log(res: dict) -> None:
    try:
        from plugins.installed.meta_commerce.models import MetaSyncLog  # noqa: PLC0415

        MetaSyncLog.objects.create(
            kind=MetaSyncLog.KIND_CAPI,
            status=MetaSyncLog.STATUS_OK if res.get('ok') else MetaSyncLog.STATUS_ERROR,
            item_count=1 if res.get('ok') else 0,
            errors=[] if res.get('ok') else [str(res.get('reason'))[:300]],
            message='CAPI Purchase',
        )
    except Exception as e:  # noqa: BLE001
        logger.debug('meta_commerce: capi log failed: %s', e)

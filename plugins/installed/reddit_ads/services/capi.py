"""Reddit Conversions API (server-side) — ad-blocker-proof conversions.

    POST /api/v2.0/conversions/events/{account_id}

Fires Purchase / AddToCart server-side with hashed email; conversion_id =
order_number so it dedupes against the browser Reddit Pixel. No-op when
unconfigured.
"""

from __future__ import annotations

import hashlib
import logging
import time

from .api import ads_connected, creds, request

logger = logging.getLogger('morpheus.reddit_ads')


def _sha256(value: str) -> str:
    return hashlib.sha256((value or '').strip().lower().encode('utf-8')).hexdigest()


def _money(m) -> tuple[float, str]:
    amount = getattr(m, 'amount', None)
    return (float(amount) if amount is not None else 0.0), str(getattr(m, 'currency', '') or 'USD')


def _line_items(obj):
    rel = getattr(obj, 'items', None)
    if rel is None:
        rel = getattr(obj, 'lines', None)
    if hasattr(rel, 'all'):
        rel = list(rel.all())
    out = []
    for line in rel or []:
        sku = (
            getattr(line, 'sku', '')
            or getattr(getattr(line, 'variant', None), 'sku', '')
            or getattr(getattr(line, 'product', None), 'sku', '')
        )
        if sku:
            out.append((sku, int(getattr(line, 'quantity', 1) or 1)))
    return out


def _send(
    tracking_type: str, *, value: float, currency: str, items, email='', conversion_id=''
) -> dict:
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    if not email:
        return {'ok': False, 'reason': 'no_user_identifier'}
    event = {
        'event_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'event_type': {'tracking_type': tracking_type},
        'user': {'email': _sha256(email)},
        'event_metadata': {
            'currency': currency,
            'value_decimal': value,
            'item_count': sum(q for _, q in items),
            'conversion_id': str(conversion_id or ''),
            'products': [{'id': sku} for sku, _ in items],
        },
    }
    res = request(
        'POST',
        f'/api/v2.0/conversions/events/{creds()["account_id"]}',
        json_body={'events': [event], 'test_mode': False},
    )
    _log(res, tracking_type)
    return res


def send_purchase(order) -> dict:
    value, currency = _money(getattr(order, 'total', None))
    return _send(
        'Purchase',
        value=value,
        currency=currency,
        items=_line_items(order),
        email=getattr(order, 'email', '') or '',
        conversion_id=str(getattr(order, 'order_number', '') or getattr(order, 'pk', '')),
    )


def _log(res: dict, tracking_type: str) -> None:
    try:
        from plugins.installed.reddit_ads.models import RedditSyncLog  # noqa: PLC0415

        RedditSyncLog.objects.create(
            kind=RedditSyncLog.KIND_CAPI,
            status=RedditSyncLog.STATUS_OK if res.get('ok') else RedditSyncLog.STATUS_ERROR,
            item_count=1 if res.get('ok') else 0,
            errors=[] if res.get('ok') else [str(res.get('reason'))[:300]],
            message=f'Conversions API {tracking_type}',
        )
    except Exception as e:  # noqa: BLE001
        logger.debug('reddit_ads: capi log failed: %s', e)

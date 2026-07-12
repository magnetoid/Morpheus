"""Pinterest Conversions API (server-side) — ad-blocker-proof conversions.

    POST /ad_accounts/{ad_account_id}/events
    { data: [{ event_name, action_source, event_time, event_id, user_data, custom_data }] }

Fires checkout / add_to_cart server-side with content_ids matched to the catalog
feed id; email SHA-256 hashed. checkout event_id = order_number so it dedupes
against the browser Pinterest Tag. No-op when unconfigured.
"""

from __future__ import annotations

import hashlib
import logging
import time

from plugins.capi_shared import line_items as _line_items
from plugins.capi_shared import money_tuple as _money

from .api import ads_connected, creds, post

logger = logging.getLogger('morpheus.pinterest_commerce')


def _sha256(value: str) -> str:
    return hashlib.sha256((value or '').strip().lower().encode('utf-8')).hexdigest()


def _send(event_name: str, *, value: float, currency: str, items, email='', event_id='') -> dict:
    c = creds()
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    user_data = {'em': [_sha256(email)]} if email else {}
    if not user_data:
        # Pinterest requires at least one user identifier; skip cleanly if none.
        return {'ok': False, 'reason': 'no_user_identifier'}
    num_items = sum(qty for _, qty in items)
    event = {
        'event_name': event_name,
        'action_source': 'web',
        'event_time': int(time.time()),
        'event_id': str(event_id or ''),
        'user_data': user_data,
        'custom_data': {
            'currency': currency,
            'value': f'{value:.2f}',
            'content_ids': [sku for sku, _ in items],
            'num_items': num_items,
        },
    }
    res = post(f'ad_accounts/{c["ad_account_id"]}/events', {'data': [event]})
    _log(res, event_name)
    return res


def send_checkout(order) -> dict:
    value, currency = _money(getattr(order, 'total', None))
    return _send(
        'checkout',
        value=value,
        currency=currency,
        items=_line_items(order),
        email=getattr(order, 'email', '') or '',
        event_id=str(getattr(order, 'order_number', '') or getattr(order, 'pk', '')),
    )


def send_add_to_cart(*, product=None, variant=None, quantity=1, email='') -> dict:
    target = variant or product
    sku = getattr(target, 'sku', '') or getattr(product, 'sku', '')
    if not sku:
        return {'ok': False, 'reason': 'no_sku'}
    value, currency = _money(getattr(target, 'price', None) or getattr(product, 'price', None))
    return _send(
        'add_to_cart',
        value=value * (quantity or 1),
        currency=currency,
        items=[(sku, quantity or 1)],
        email=email,
    )


def _log(res: dict, event: str) -> None:
    try:
        from plugins.installed.pinterest_commerce.models import PinterestSyncLog  # noqa: PLC0415

        PinterestSyncLog.objects.create(
            kind=PinterestSyncLog.KIND_CAPI,
            status=PinterestSyncLog.STATUS_OK if res.get('ok') else PinterestSyncLog.STATUS_ERROR,
            item_count=1 if res.get('ok') else 0,
            errors=[] if res.get('ok') else [str(res.get('reason'))[:300]],
            message=f'Conversions API {event}',
        )
    except Exception as e:  # noqa: BLE001
        logger.debug('pinterest_commerce: capi log failed: %s', e)

"""Snapchat Conversions API (CAPI) — server-side Purchase events.

    POST https://tr.snapchat.com/v3/{pixel_id}/events   (Bearer access token)

Fires PURCHASE server-side with a SHA-256 hashed email; event_id = order_number
so it dedupes against the browser snaptr PURCHASE. No-op when unconfigured.
Best-effort until validated with live credentials — every path fails soft.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time

from plugins.capi_shared import line_items as _line_items
from plugins.capi_shared import money_tuple as _money

from .api import creds
from .oauth import access_token, is_connected

logger = logging.getLogger('morpheus.snapchat_commerce')

_CAPI_BASE = 'https://tr.snapchat.com/v3'
_PIXEL_RE = re.compile(r'^[A-Za-z0-9-]{6,64}$')


def capi_connected() -> bool:
    return bool(is_connected() and _PIXEL_RE.match(creds()['pixel_id'] or ''))


def _sha256(value: str) -> str:
    return hashlib.sha256((value or '').strip().lower().encode('utf-8')).hexdigest()


def _post(event: dict) -> dict:
    if not capi_connected():
        return {'ok': False, 'reason': 'not_connected'}
    token = access_token()
    if not token:
        return {'ok': False, 'reason': 'no_access_token'}
    try:
        import requests  # noqa: PLC0415

        resp = requests.post(
            f'{_CAPI_BASE}/{creds()["pixel_id"]}/events',
            json={'data': [event]},
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            timeout=15,
        )
        resp.raise_for_status()
        return {'ok': True, 'data': resp.json() if resp.content else {}}
    except Exception as e:  # noqa: BLE001 — never block the order flow
        reason = _err(e)
        logger.warning('snapchat_commerce: CAPI post failed: %s', reason)
        return {'ok': False, 'reason': reason}


def send_purchase(order) -> dict:
    if not capi_connected():
        return {'ok': False, 'reason': 'not_connected'}
    email = getattr(order, 'email', '') or ''
    if not email:
        return {'ok': False, 'reason': 'no_user_identifier'}
    value, currency = _money(getattr(order, 'total', None))
    items = _line_items(order)
    onum = str(getattr(order, 'order_number', '') or getattr(order, 'pk', ''))
    event = {
        'event_name': 'PURCHASE',
        'event_time': int(time.time()),
        'action_source': 'WEB',
        'event_id': onum,
        'user_data': {'em': [_sha256(email)]},
        'custom_data': {
            'currency': currency,
            'value': str(value),
            'num_items': sum(q for _, q in items),
            'content_ids': [sku for sku, _ in items],
            'content_type': 'product',
            'order_id': onum,
        },
    }
    res = _post(event)
    _log(res, 'PURCHASE')
    return res


def _log(res: dict, event_name: str) -> None:
    try:
        from plugins.installed.snapchat_commerce.models import SnapchatSyncLog  # noqa: PLC0415

        SnapchatSyncLog.objects.create(
            kind=SnapchatSyncLog.KIND_CAPI,
            status=SnapchatSyncLog.STATUS_OK if res.get('ok') else SnapchatSyncLog.STATUS_ERROR,
            item_count=1 if res.get('ok') else 0,
            errors=[] if res.get('ok') else [str(res.get('reason'))[:300]],
            message=f'Conversions API {event_name}',
        )
    except Exception as e:  # noqa: BLE001
        logger.debug('snapchat_commerce: capi log failed: %s', e)


def _err(e) -> str:
    resp = getattr(e, 'response', None)
    if resp is not None:
        try:
            return str(resp.json())[:300]
        except Exception:  # noqa: BLE001
            return str(e)[:300]
    return str(e)[:300]

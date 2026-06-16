"""Reddit Ads API REST client (ads-api.reddit.com).

Bearer access token (OAuth) + required User-Agent. Token in headers, never a
URL. Graceful {ok: False, reason} when not connected.
"""

from __future__ import annotations

import logging

from .oauth import USER_AGENT, access_token, is_connected
from .settings import raw_config

logger = logging.getLogger('morpheus.reddit_ads')

BASE = 'https://ads-api.reddit.com'


def creds() -> dict:
    cfg = raw_config()
    return {
        'account_id': (cfg.get('account_id') or '').strip(),
        'pixel_id': (cfg.get('pixel_id') or '').strip(),
    }


def ads_connected() -> bool:
    return bool(is_connected() and creds()['account_id'])


def _headers() -> dict | None:
    token = access_token()
    if not token:
        return None
    return {
        'Authorization': f'Bearer {token}',
        'User-Agent': USER_AGENT,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }


def request(method: str, path: str, *, json_body=None) -> dict:
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    headers = _headers()
    if headers is None:
        return {'ok': False, 'reason': 'no_access_token'}
    try:
        import requests  # noqa: PLC0415

        resp = requests.request(
            method, f'{BASE}{path}', json=json_body, headers=headers, timeout=30
        )
        resp.raise_for_status()
        return {'ok': True, 'data': resp.json() if resp.content else {}}
    except Exception as e:  # noqa: BLE001
        logger.warning('reddit_ads: %s %s failed: %s', method, path, _err(e))
        return {'ok': False, 'reason': _err(e)}


def verify_connection() -> dict:
    if not is_connected():
        return {'token': {'ok': False, 'detail': 'No OAuth refresh token set.'}}
    if not creds()['account_id']:
        return {
            'token': {'ok': True, 'detail': 'Token set'},
            'account': {'ok': False, 'detail': 'Set an ad account ID.'},
        }
    res = request('GET', f'/api/v3/ad_accounts/{creds()["account_id"]}')
    if res.get('ok'):
        data = (res['data'] or {}).get('data', res['data'])
        name = data.get('name') if isinstance(data, dict) else ''
        return {
            'token': {'ok': True, 'detail': 'Token valid.'},
            'account': {'ok': True, 'detail': name or 'OK'},
        }
    return {'token': {'ok': False, 'detail': res.get('reason', 'invalid')}}


def _err(e) -> str:
    resp = getattr(e, 'response', None)
    if resp is not None:
        try:
            return str(resp.json())[:300]
        except Exception:  # noqa: BLE001
            return str(e)[:300]
    return str(e)[:300]

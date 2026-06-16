"""Snapchat Marketing API REST client (adsapi.snapchat.com/v1).

Bearer access token (OAuth) in the header. Graceful {ok: False, reason} when not
connected.
"""

from __future__ import annotations

import logging

from .oauth import access_token, is_connected
from .settings import raw_config

logger = logging.getLogger('morpheus.snapchat_commerce')

BASE = 'https://adsapi.snapchat.com/v1'


def creds() -> dict:
    cfg = raw_config()
    return {
        'ad_account_id': (cfg.get('ad_account_id') or '').strip(),
        'pixel_id': (cfg.get('pixel_id') or '').strip(),
    }


def ads_connected() -> bool:
    return bool(is_connected() and creds()['ad_account_id'])


def _headers() -> dict | None:
    token = access_token()
    if not token:
        return None
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


def request(method: str, path: str, *, json_body=None, params=None) -> dict:
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    headers = _headers()
    if headers is None:
        return {'ok': False, 'reason': 'no_access_token'}
    try:
        import requests  # noqa: PLC0415

        resp = requests.request(
            method, f'{BASE}{path}', json=json_body, params=params, headers=headers, timeout=30
        )
        resp.raise_for_status()
        return {'ok': True, 'data': resp.json() if resp.content else {}}
    except Exception as e:  # noqa: BLE001
        logger.warning('snapchat_commerce: %s %s failed: %s', method, path, _err(e))
        return {'ok': False, 'reason': _err(e)}


def verify_connection() -> dict:
    if not is_connected():
        return {'token': {'ok': False, 'detail': 'No OAuth refresh token set.'}}
    if not creds()['ad_account_id']:
        return {
            'token': {'ok': True, 'detail': 'Token set'},
            'ad_account': {'ok': False, 'detail': 'Set an ad account ID.'},
        }
    res = request('GET', f'/adaccounts/{creds()["ad_account_id"]}')
    if res.get('ok'):
        accts = (res['data'] or {}).get('adaccounts') or [{}]
        name = (accts[0].get('adaccount') or {}).get('name', '') if accts else ''
        return {
            'token': {'ok': True, 'detail': 'Token valid.'},
            'ad_account': {'ok': True, 'detail': name or 'OK'},
        }
    return {'token': {'ok': False, 'detail': res.get('reason', 'invalid')}}


def _err(e) -> str:
    resp = getattr(e, 'response', None)
    if resp is not None:
        try:
            body = resp.json()
            return str(body.get('debug_message') or body.get('error') or body)[:300]
        except Exception:  # noqa: BLE001
            return str(e)[:300]
    return str(e)[:300]

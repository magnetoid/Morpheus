"""Shared Pinterest API v5 helpers — Bearer token + ad_account_id from
PluginConfig. Token rides the Authorization header (never a URL). Every caller
degrades to {ok: False, reason} when not connected.
"""

from __future__ import annotations

import logging

from .settings import raw_config

logger = logging.getLogger('morpheus.pinterest_commerce')

BASE = 'https://api.pinterest.com/v5'


def creds() -> dict:
    cfg = raw_config()
    return {
        'access_token': (cfg.get('access_token') or '').strip(),
        'ad_account_id': (cfg.get('ad_account_id') or '').strip(),
        'catalog_feed_id': (cfg.get('catalog_feed_id') or '').strip(),
        'tag_id': (cfg.get('tag_id') or '').strip(),
    }


def has_token() -> bool:
    return bool(creds()['access_token'])


def ads_connected() -> bool:
    c = creds()
    return bool(c['access_token'] and c['ad_account_id'])


def _headers() -> dict:
    return {
        'Authorization': f'Bearer {creds()["access_token"]}',
        'Content-Type': 'application/json',
    }


def get(path: str, params: dict | None = None) -> dict:
    if not has_token():
        return {'ok': False, 'reason': 'not_connected'}
    try:
        import requests  # noqa: PLC0415

        resp = requests.get(f'{BASE}/{path}', params=params or {}, headers=_headers(), timeout=30)
        resp.raise_for_status()
        return {'ok': True, 'data': resp.json()}
    except Exception as e:  # noqa: BLE001
        logger.warning('pinterest_commerce: GET %s failed: %s', path, _err(e))
        return {'ok': False, 'reason': _err(e)}


def post(path: str, payload: dict) -> dict:
    if not has_token():
        return {'ok': False, 'reason': 'not_connected'}
    try:
        import requests  # noqa: PLC0415

        resp = requests.post(f'{BASE}/{path}', json=payload, headers=_headers(), timeout=30)
        resp.raise_for_status()
        return {'ok': True, 'data': resp.json()}
    except Exception as e:  # noqa: BLE001
        logger.warning('pinterest_commerce: POST %s failed: %s', path, _err(e))
        return {'ok': False, 'reason': _err(e)}


def patch(path: str, payload) -> dict:
    if not has_token():
        return {'ok': False, 'reason': 'not_connected'}
    try:
        import requests  # noqa: PLC0415

        resp = requests.patch(f'{BASE}/{path}', json=payload, headers=_headers(), timeout=30)
        resp.raise_for_status()
        return {'ok': True, 'data': resp.json()}
    except Exception as e:  # noqa: BLE001
        logger.warning('pinterest_commerce: PATCH %s failed: %s', path, _err(e))
        return {'ok': False, 'reason': _err(e)}


def verify_connection() -> dict:
    c = creds()
    if not c['access_token']:
        return {'token': {'ok': False, 'detail': 'No access token set.'}}
    out: dict = {}
    r = get('user_account')
    out['token'] = (
        {'ok': True, 'detail': r['data'].get('username', 'Token valid.')}
        if r.get('ok')
        else {'ok': False, 'detail': r.get('reason', 'invalid')}
    )
    if c['ad_account_id']:
        ra = get(f'ad_accounts/{c["ad_account_id"]}')
        out['ad_account'] = (
            {'ok': True, 'detail': ra['data'].get('name', 'OK')}
            if ra.get('ok')
            else {'ok': False, 'detail': ra.get('reason', 'invalid')}
        )
    return out


def _err(e) -> str:
    resp = getattr(e, 'response', None)
    if resp is not None:
        try:
            return str(resp.json().get('message', e))[:300]
        except Exception:  # noqa: BLE001
            return str(e)[:300]
    return str(e)[:300]

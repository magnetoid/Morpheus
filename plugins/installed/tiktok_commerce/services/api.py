"""Shared TikTok for Business (Marketing API v1.3) helpers.

Auth is a long-lived access token + advertiser_id, all from PluginConfig. The
token rides in the `Access-Token` HEADER (not the URL), so it never lands in a
logged URL. TikTok responses are `{code, message, data}` — code 0 = success.
Every caller degrades to `{ok: False, reason}` when not connected.
"""

from __future__ import annotations

import logging

from .settings import raw_config

logger = logging.getLogger('morpheus.tiktok_commerce')

BASE = 'https://business-api.tiktok.com/open_api/v1.3'


def creds() -> dict:
    cfg = raw_config()
    return {
        'access_token': (cfg.get('access_token') or '').strip(),
        'advertiser_id': (cfg.get('advertiser_id') or '').strip(),
        'catalog_id': (cfg.get('catalog_id') or '').strip(),
        'pixel_code': (cfg.get('pixel_code') or '').strip(),
    }


def has_token() -> bool:
    return bool(creds()['access_token'])


def ads_connected() -> bool:
    c = creds()
    return bool(c['access_token'] and c['advertiser_id'])


def catalog_connected() -> bool:
    c = creds()
    return bool(c['access_token'] and c['catalog_id'])


def _headers() -> dict:
    return {'Access-Token': creds()['access_token'], 'Content-Type': 'application/json'}


def _unwrap(resp) -> dict:
    """TikTok wraps everything in {code, message, data}; code 0 = success."""
    body = resp.json()
    if body.get('code') not in (0, None):
        return {'ok': False, 'reason': str(body.get('message') or body.get('code'))[:300]}
    return {'ok': True, 'data': body.get('data', {})}


def get(path: str, params: dict | None = None) -> dict:
    if not has_token():
        return {'ok': False, 'reason': 'not_connected'}
    try:
        import requests  # noqa: PLC0415

        resp = requests.get(f'{BASE}/{path}', params=params or {}, headers=_headers(), timeout=30)
        resp.raise_for_status()
        return _unwrap(resp)
    except Exception as e:  # noqa: BLE001
        logger.warning('tiktok_commerce: GET %s failed: %s', path, _err(e))
        return {'ok': False, 'reason': _err(e)}


def post(path: str, payload: dict) -> dict:
    if not has_token():
        return {'ok': False, 'reason': 'not_connected'}
    try:
        import requests  # noqa: PLC0415

        resp = requests.post(f'{BASE}/{path}', json=payload, headers=_headers(), timeout=30)
        resp.raise_for_status()
        return _unwrap(resp)
    except Exception as e:  # noqa: BLE001
        logger.warning('tiktok_commerce: POST %s failed: %s', path, _err(e))
        return {'ok': False, 'reason': _err(e)}


def verify_connection() -> dict:
    """Validate the token + advertiser via real API calls. {check: {ok, detail}}."""
    c = creds()
    if not c['access_token']:
        return {'token': {'ok': False, 'detail': 'No access token set.'}}
    out: dict = {}
    if c['advertiser_id']:
        r = get('advertiser/info/', {'advertiser_ids': f'["{c["advertiser_id"]}"]'})
        if r.get('ok'):
            lst = (r['data'] or {}).get('list') or [{}]
            out['advertiser'] = {'ok': True, 'detail': lst[0].get('name', 'OK')}
            out['token'] = {'ok': True, 'detail': 'Token valid.'}
        else:
            out['token'] = {'ok': False, 'detail': r.get('reason', 'invalid')}
    else:
        # No advertiser to probe with — at least confirm the token shape works.
        out['token'] = {'ok': True, 'detail': 'Token set (add advertiser ID to validate).'}
    return out


def _err(e) -> str:
    resp = getattr(e, 'response', None)
    if resp is not None:
        try:
            return str(resp.json().get('message', e))[:300]
        except Exception:  # noqa: BLE001
            return str(e)[:300]
    return str(e)[:300]

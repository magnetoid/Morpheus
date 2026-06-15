"""Shared Meta Graph API helpers — connection state + low-level GET/POST.

Auth is a long-lived **System User access token** (no OAuth refresh dance), plus
IDs, all from PluginConfig. Every caller degrades to a structured
`{ok: False, reason: ...}` when not connected, so dashboards render a "connect"
state instead of erroring.
"""

from __future__ import annotations

import logging

from .settings import raw_config

logger = logging.getLogger('morpheus.meta_commerce')

API_VERSION = 'v21.0'
GRAPH = f'https://graph.facebook.com/{API_VERSION}'


def creds() -> dict:
    cfg = raw_config()
    return {
        'access_token': (cfg.get('access_token') or '').strip(),
        'catalog_id': (cfg.get('catalog_id') or '').strip(),
        'ad_account_id': (cfg.get('ad_account_id') or '').strip().removeprefix('act_'),
        'pixel_id': (cfg.get('pixel_id') or '').strip(),
        'business_id': (cfg.get('business_id') or '').strip(),
    }


def has_token() -> bool:
    return bool(creds()['access_token'])


def catalog_connected() -> bool:
    c = creds()
    return bool(c['access_token'] and c['catalog_id'])


def ads_connected() -> bool:
    c = creds()
    return bool(c['access_token'] and c['ad_account_id'])


def get(path: str, params: dict | None = None) -> dict:
    """GET {GRAPH}/{path}. Returns {ok, data} or {ok: False, reason}."""
    if not has_token():
        return {'ok': False, 'reason': 'not_connected'}
    try:
        import requests  # noqa: PLC0415

        p = dict(params or {})
        p['access_token'] = creds()['access_token']
        resp = requests.get(f'{GRAPH}/{path}', params=p, timeout=30)
        resp.raise_for_status()
        return {'ok': True, 'data': resp.json()}
    except Exception as e:  # noqa: BLE001
        logger.warning('meta_commerce: GET %s failed: %s', path, _err(e))
        return {'ok': False, 'reason': _err(e)}


def post(path: str, payload: dict) -> dict:
    """POST {GRAPH}/{path} (form-encoded). Returns {ok, data} or {ok: False}."""
    if not has_token():
        return {'ok': False, 'reason': 'not_connected'}
    try:
        import requests  # noqa: PLC0415

        body = dict(payload)
        body['access_token'] = creds()['access_token']
        resp = requests.post(f'{GRAPH}/{path}', data=body, timeout=30)
        resp.raise_for_status()
        return {'ok': True, 'data': resp.json()}
    except Exception as e:  # noqa: BLE001
        logger.warning('meta_commerce: POST %s failed: %s', path, _err(e))
        return {'ok': False, 'reason': _err(e)}


def _err(e) -> str:
    # Surface Meta's error message body when present (it's the useful part).
    resp = getattr(e, 'response', None)
    if resp is not None:
        try:
            return _redact(str(resp.json().get('error', {}).get('message', e)))[:300]
        except Exception:  # noqa: BLE001
            return _redact(str(e))[:300]
    return _redact(str(e))[:300]


def _redact(s: str) -> str:
    """Strip any access_token=… from a string before it reaches a log — the
    GET URL carries the token as a query param, so a raised HTTPError's repr
    would otherwise leak it into log aggregators."""
    import re  # noqa: PLC0415

    return re.sub(r'access_token=[^&\s]+', 'access_token=REDACTED', s)

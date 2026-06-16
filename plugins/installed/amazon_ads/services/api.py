"""Amazon Advertising API REST client — region base + auth headers.

Auth: Bearer access token (LWA) + Amazon-Advertising-API-ClientId +
Amazon-Advertising-API-Scope (profile_id). Token in headers, never a URL.
Graceful {ok: False, reason} when not connected.
"""

from __future__ import annotations

import logging

from .oauth import access_token, is_connected, oauth_config
from .settings import raw_config

logger = logging.getLogger('morpheus.amazon_ads')

_REGION_BASE = {
    'na': 'https://advertising-api.amazon.com',
    'eu': 'https://advertising-api-eu.amazon.com',
    'fe': 'https://advertising-api-fe.amazon.com',
}


def creds() -> dict:
    cfg = raw_config()
    return {
        'profile_id': (cfg.get('profile_id') or '').strip(),
        'region': (cfg.get('region') or 'na').strip().lower(),
    }


def base_url() -> str:
    return _REGION_BASE.get(creds()['region'], _REGION_BASE['na'])


def ads_connected() -> bool:
    return bool(is_connected() and creds()['profile_id'])


def _headers(extra: dict | None = None) -> dict | None:
    token = access_token()
    if not token:
        return None
    h = {
        'Authorization': f'Bearer {token}',
        'Amazon-Advertising-API-ClientId': oauth_config()['client_id'],
        'Amazon-Advertising-API-Scope': creds()['profile_id'],
        'Content-Type': 'application/json',
    }
    if extra:
        h.update(extra)
    return h


def request(method: str, path: str, *, json_body=None, headers_extra=None) -> dict:
    """REST call to the Ads API. Returns {ok, data} or {ok: False, reason}."""
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    headers = _headers(headers_extra)
    if headers is None:
        return {'ok': False, 'reason': 'no_access_token'}
    try:
        import requests  # noqa: PLC0415

        resp = requests.request(
            method, f'{base_url()}{path}', json=json_body, headers=headers, timeout=30
        )
        resp.raise_for_status()
        data = resp.json() if resp.content else {}
        return {'ok': True, 'data': data}
    except Exception as e:  # noqa: BLE001
        logger.warning('amazon_ads: %s %s failed: %s', method, path, _err(e))
        return {'ok': False, 'reason': _err(e)}


def list_profiles() -> dict:
    """GET /v2/profiles — used to discover/verify the profile_id."""
    if not is_connected():
        return {'ok': False, 'reason': 'not_connected'}
    token = access_token()
    if not token:
        return {'ok': False, 'reason': 'no_access_token'}
    try:
        import requests  # noqa: PLC0415

        resp = requests.get(
            f'{base_url()}/v2/profiles',
            headers={
                'Authorization': f'Bearer {token}',
                'Amazon-Advertising-API-ClientId': oauth_config()['client_id'],
            },
            timeout=30,
        )
        resp.raise_for_status()
        return {'ok': True, 'data': resp.json()}
    except Exception as e:  # noqa: BLE001
        return {'ok': False, 'reason': _err(e)}


def verify_connection() -> dict:
    """Validate token + profile via GET /v2/profiles. {check: {ok, detail}}."""
    if not is_connected():
        return {'token': {'ok': False, 'detail': 'No OAuth refresh token set.'}}
    out: dict = {}
    r = list_profiles()
    if not r.get('ok'):
        return {'token': {'ok': False, 'detail': r.get('reason', 'invalid')}}
    out['token'] = {'ok': True, 'detail': 'Token valid.'}
    pid = creds()['profile_id']
    profiles = r['data'] if isinstance(r['data'], list) else []
    match = next((p for p in profiles if str(p.get('profileId')) == pid), None)
    if pid:
        out['profile'] = (
            {
                'ok': True,
                'detail': f'{match.get("countryCode", "?")} ({match.get("accountInfo", {}).get("type", "")})',
            }
            if match
            else {'ok': False, 'detail': 'profile_id not found among your profiles'}
        )
    else:
        ids = ', '.join(str(p.get('profileId')) for p in profiles[:5])
        out['profile'] = {'ok': False, 'detail': f'Set a profile_id. Available: {ids or "none"}'}
    return out


def _err(e) -> str:
    resp = getattr(e, 'response', None)
    if resp is not None:
        try:
            body = resp.json()
            return str(body.get('details') or body.get('message') or body.get('code') or e)[:300]
        except Exception:  # noqa: BLE001
            return str(e)[:300]
    return str(e)[:300]

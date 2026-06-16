"""Microsoft identity OAuth2 — refresh-token → access token for the Ads API.

Mirrors the Google flow: client_id/secret/refresh_token → access_token, cached.
Thin REST over `requests`. Creds in PluginConfig only. None when not configured.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.microsoft_commerce')

_TOKEN_URL = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'
_SCOPE = 'https://ads.microsoft.com/msads.manage offline_access'
_CACHE_KEY = 'microsoft_commerce:access_token:v1'
_TTL = 50 * 60


def oauth_config() -> dict:
    from .settings import raw_config  # noqa: PLC0415

    cfg = raw_config()
    return {
        'client_id': (cfg.get('oauth_client_id') or '').strip(),
        'client_secret': (cfg.get('oauth_client_secret') or '').strip(),
        'refresh_token': (cfg.get('oauth_refresh_token') or '').strip(),
    }


def is_connected() -> bool:
    c = oauth_config()
    return bool(c['client_id'] and c['client_secret'] and c['refresh_token'])


def access_token(*, force: bool = False) -> str | None:
    if not is_connected():
        return None
    from django.core.cache import cache  # noqa: PLC0415

    if not force:
        cached = cache.get(_CACHE_KEY)
        if cached:
            return cached
    c = oauth_config()
    try:
        import requests  # noqa: PLC0415

        resp = requests.post(
            _TOKEN_URL,
            data={
                'client_id': c['client_id'],
                'client_secret': c['client_secret'],
                'refresh_token': c['refresh_token'],
                'grant_type': 'refresh_token',
                'scope': _SCOPE,
            },
            timeout=10,
        )
        resp.raise_for_status()
        token = resp.json().get('access_token')
    except Exception as e:  # noqa: BLE001
        logger.warning('microsoft_commerce: token refresh failed: %s', e)
        return None
    if token:
        cache.set(_CACHE_KEY, token, _TTL)
    return token

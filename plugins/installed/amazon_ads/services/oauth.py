"""Login with Amazon OAuth2 — refresh-token → access token for the Ads API."""

from __future__ import annotations

import logging

from .settings import raw_config

logger = logging.getLogger('morpheus.amazon_ads')

_TOKEN_URL = 'https://api.amazon.com/auth/o2/token'
_CACHE_KEY = 'amazon_ads:access_token:v1'
_TTL = 50 * 60


def oauth_config() -> dict:
    cfg = raw_config()
    return {
        'client_id': (cfg.get('client_id') or '').strip(),
        'client_secret': (cfg.get('client_secret') or '').strip(),
        'refresh_token': (cfg.get('refresh_token') or '').strip(),
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
                'grant_type': 'refresh_token',
                'refresh_token': c['refresh_token'],
                'client_id': c['client_id'],
                'client_secret': c['client_secret'],
            },
            timeout=10,
        )
        resp.raise_for_status()
        token = resp.json().get('access_token')
    except Exception as e:  # noqa: BLE001
        logger.warning('amazon_ads: token refresh failed: %s', e)
        return None
    if token:
        cache.set(_CACHE_KEY, token, _TTL)
    return token

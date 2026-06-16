"""Reddit OAuth2 — refresh-token → access token (HTTP-basic client auth).

Reddit requires a descriptive User-Agent on every call. Token cached. None when
not configured.
"""

from __future__ import annotations

import logging

from .settings import raw_config

logger = logging.getLogger('morpheus.reddit_ads')

_TOKEN_URL = 'https://www.reddit.com/api/v1/access_token'
_CACHE_KEY = 'reddit_ads:access_token:v1'
_TTL = 50 * 60
USER_AGENT = 'morpheus-commerce/1.0 (+https://dotbooks.store)'


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
            auth=(c['client_id'], c['client_secret']),
            data={'grant_type': 'refresh_token', 'refresh_token': c['refresh_token']},
            headers={'User-Agent': USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        token = resp.json().get('access_token')
    except Exception as e:  # noqa: BLE001
        logger.warning('reddit_ads: token refresh failed: %s', e)
        return None
    if token:
        cache.set(_CACHE_KEY, token, _TTL)
    return token

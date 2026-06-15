"""OAuth2 access tokens for the Google Content API + Google Ads API.

Uses the **refresh-token** flow (client_id / client_secret / refresh_token →
access_token), which works for both APIs and needs only `requests` — no
service-account JWT signing, no heavyweight Google SDK. The merchant obtains a
refresh token once via the OAuth consent screen and pastes the three values into
the settings panel (stored in PluginConfig, never settings.py).

`access_token()` returns a cached token (Django cache, ~50 min) or None when the
plugin isn't configured — every API caller treats None as "not connected" and
degrades gracefully.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.google_shopping')

_TOKEN_URL = 'https://oauth2.googleapis.com/token'
_CACHE_KEY = 'google_shopping:access_token:v1'
_TOKEN_TTL = 50 * 60  # tokens last 1h; refresh a little early


def oauth_config() -> dict:
    """The OAuth client config from PluginConfig (empty strings when unset)."""
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
    """A valid OAuth2 access token, or None when not configured / on failure."""
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
            },
            timeout=10,
        )
        resp.raise_for_status()
        token = resp.json().get('access_token')
    except Exception as e:  # noqa: BLE001 — never raise into a request/task
        logger.warning('google_shopping: token refresh failed: %s', e)
        return None

    if token:
        cache.set(_CACHE_KEY, token, _TOKEN_TTL)
    return token

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
_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
_CACHE_KEY = 'google_shopping:access_token:v1'
_TOKEN_TTL = 50 * 60  # tokens last 1h; refresh a little early
# Content API (Merchant) + Google Ads — one consent grants both.
_SCOPES = 'https://www.googleapis.com/auth/content https://www.googleapis.com/auth/adwords'


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


def has_client() -> bool:
    """True once the OAuth client (id+secret) is set — enough to start consent."""
    c = oauth_config()
    return bool(c['client_id'] and c['client_secret'])


def authorize_url(redirect_uri: str, state: str = '') -> str | None:
    """The Google consent URL to start the connect flow, or None if no client.

    `state` is an anti-CSRF token the caller stores in the session and
    re-verifies in the callback (prevents login-CSRF — an attacker connecting
    the merchant's store to the attacker's Google account)."""
    c = oauth_config()
    if not (c['client_id'] and c['client_secret']):
        return None
    from urllib.parse import urlencode  # noqa: PLC0415

    params = {
        'client_id': c['client_id'],
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': _SCOPES,
        'access_type': 'offline',  # ask for a refresh token
        'prompt': 'consent',  # force a fresh refresh token even on re-consent
        'include_granted_scopes': 'true',
    }
    if state:
        params['state'] = state
    return f'{_AUTH_URL}?{urlencode(params)}'


def exchange_code(code: str, redirect_uri: str) -> dict:
    """Exchange an auth code for tokens and persist the refresh token."""
    c = oauth_config()
    if not (c['client_id'] and c['client_secret'] and code):
        return {'ok': False, 'reason': 'missing_client_or_code'}
    try:
        import requests  # noqa: PLC0415

        resp = requests.post(
            _TOKEN_URL,
            data={
                'code': code,
                'client_id': c['client_id'],
                'client_secret': c['client_secret'],
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code',
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        logger.warning('google_shopping: code exchange failed: %s', e)
        return {'ok': False, 'reason': str(e)[:200]}

    refresh = data.get('refresh_token')
    if not refresh:
        # Google omits the refresh token if the user already granted consent
        # without prompt=consent; we force prompt=consent above to avoid this.
        return {'ok': False, 'reason': 'no_refresh_token'}
    _store_refresh_token(refresh)
    return {'ok': True}


def _store_refresh_token(refresh: str) -> None:
    from .settings import _plugin  # noqa: PLC0415

    p = _plugin()
    if p is not None:
        p.set_config('oauth_refresh_token', refresh)
        p.invalidate_config_cache()


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

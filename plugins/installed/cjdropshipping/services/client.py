"""A small client for the CJdropshipping Open API 2.0.

Contract (official docs, developers.cjdropshipping.com, read 2026-10-10;
digest in docs/plans/cj-aliexpress-dropshipping.md):

* base ``https://developers.cjdropshipping.com/api2.0/v1``; every call sends
  ``CJ-Access-Token`` and ``Content-Type: application/json``;
* ``POST /authentication/getAccessToken {"apiKey"}`` → ``data.accessToken``,
  ``data.openId`` (also the webhook signing secret). Tokens live 180 days and
  CJ returns the same one for 24 h; the call itself is limited to once a second;
* success is "HTTP 200 and (code == 200 or no code)", anything else a failure —
  never trust ``message`` text, it changes; 1600001/1600002 mean a bad or
  missing token (fetch a new one once and retry);
* per-account rate 1–6 requests/second by account level, plus a daily points
  budget (search 50 points, detail/stock/freight 10, orders free).

The token and openId are cached (shared Redis in production), never written
to the database: the API key in the settings panel is the only stored secret.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

logger = logging.getLogger('morpheus.cjdropshipping')

BASE_URL = 'https://developers.cjdropshipping.com/api2.0/v1'
TIMEOUT = 30
TOKEN_TTL = 60 * 60 * 24 * 30  # re-fetched long before CJ's 180 days
_MIN_INTERVAL = 1.05  # the free tier's one request a second
_AUTH_CODES = {1600001, 1600002}


class CJError(Exception):
    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message


def config() -> dict:
    from plugins.registry import app_registry  # noqa: PLC0415

    plugin = app_registry.get('cjdropshipping')
    if plugin is None:
        return {}
    try:
        plugin.invalidate_config_cache()  # a worker must see a key saved on the web
    except Exception:  # noqa: BLE001
        logger.debug('cjdropshipping: config cache not invalidated', exc_info=True)
    return plugin.get_config() or {}


def api_key() -> str:
    return str(config().get('api_key') or '').strip()


def _key_id(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _throttle() -> None:
    from django.core.cache import cache  # noqa: PLC0415

    last = cache.get('cj:last_call') or 0.0
    wait = _MIN_INTERVAL - (time.time() - float(last))
    if wait > 0:
        time.sleep(min(wait, _MIN_INTERVAL))
    cache.set('cj:last_call', time.time(), timeout=60)


def _parse(resp) -> Any:
    try:
        body = resp.json()
    except ValueError as e:
        raise CJError(f'CJ answered HTTP {resp.status_code} without JSON.') from e
    code = body.get('code') if isinstance(body, dict) else None
    if resp.status_code == 200 and (code is None or code == 200):  # noqa: PLR2004
        return body.get('data')
    message = (body.get('message') if isinstance(body, dict) else '') or f'HTTP {resp.status_code}'
    raise CJError(str(message), code if isinstance(code, int) else None)


def credentials(*, force: bool = False) -> dict:
    """``{'access_token', 'open_id'}`` for the configured API key."""
    from django.core.cache import cache  # noqa: PLC0415

    key = api_key()
    if not key:
        raise CJError('No CJ API key — add it under Settings → Shipping → CJdropshipping.')
    cache_key = f'cj:token:{_key_id(key)}'
    cached = None if force else cache.get(cache_key)
    if cached:
        return cached
    import requests  # noqa: PLC0415

    _throttle()
    try:
        resp = requests.post(
            f'{BASE_URL}/authentication/getAccessToken',
            json={'apiKey': key},
            headers={'Content-Type': 'application/json'},
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        raise CJError(f'CJ is unreachable: {e}') from e
    data = _parse(resp) or {}
    creds = {
        'access_token': data.get('accessToken') or '',
        'open_id': str(data.get('openId') or ''),
    }
    if not creds['access_token']:
        raise CJError('CJ returned no access token.')
    cache.set(cache_key, creds, timeout=TOKEN_TTL)
    return creds


def open_id() -> str:
    """The account's openId — the secret CJ signs its webhooks with."""
    return credentials().get('open_id', '')


def request(method: str, path: str, *, params: dict | None = None, json: Any = None) -> Any:
    """Call ``path`` and return ``data``; raises :class:`CJError`."""
    import requests  # noqa: PLC0415

    for attempt in (1, 2):
        token = credentials(force=attempt == 2)['access_token']  # noqa: PLR2004
        _throttle()
        try:
            resp = requests.request(
                method,
                f'{BASE_URL}{path}',
                params=params,
                json=json,
                headers={'CJ-Access-Token': token, 'Content-Type': 'application/json'},
                timeout=TIMEOUT,
            )
        except requests.RequestException as e:
            raise CJError(f'CJ is unreachable: {e}') from e
        try:
            return _parse(resp)
        except CJError as e:
            if e.code in _AUTH_CODES and attempt == 1:
                continue
            raise
    raise CJError('CJ rejected the access token twice.')

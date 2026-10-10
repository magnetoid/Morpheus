"""A client for the AliExpress Open Platform (IOP) — dropshipping methods + OAuth.

Contract (official docs on openservice.aliexpress.com and the official
Java/Python/PHP SDKs, read 2026-10-10; digest in
docs/plans/cj-aliexpress-dropshipping.md):

* business methods: ``POST https://api-sg.aliexpress.com/sync`` with
  ``method=<dotted name>``; system methods (OAuth): ``POST
  https://api-sg.aliexpress.com/rest/auth/token/create`` and ``…/refresh``;
* system parameters ``app_key``, ``timestamp`` (epoch milliseconds),
  ``sign_method=sha256``, ``sign``, and the merchant's ``access_token``;
* ``sign`` = uppercase hex HMAC-SHA256(key = AppSecret) over every sent
  parameter except ``sign``, empty values skipped, sorted by name in ASCII
  order, concatenated as ``key+value``; for a system method the API path is
  put in front (official vectors in tests);
* errors arrive as ``{"error_response": {"code", "msg", "sub_code", …}}``;
  business failures often come back as HTTP 200 with flags inside ``result``;
* without ``simplify`` the payload is wrapped in ``<method>_response`` and lists
  in ``{"<item_name>": [...]}`` — :func:`unwrap` normalises both shapes.

The merchant's tokens (``access_token`` 30 days, ``refresh_token`` 60 days once
the app is launched; 1 and 2 days while it is in testing) are kept on the app's
own config row, outside the settings schema, so a settings save never touches
them.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any

logger = logging.getLogger('morpheus.aliexpress')

GATEWAY = 'https://api-sg.aliexpress.com'
AUTHORIZE_URL = f'{GATEWAY}/oauth/authorize'
TIMEOUT = 30
REFRESH_MARGIN_MS = 2 * 24 * 60 * 60 * 1000  # refresh when under two days are left


class AEError(Exception):
    def __init__(self, message: str, code: str = ''):
        super().__init__(message)
        self.code = code
        self.message = message


def _plugin():
    from plugins.registry import app_registry  # noqa: PLC0415

    return app_registry.get('aliexpress')


def config() -> dict:
    plugin = _plugin()
    if plugin is None:
        return {}
    try:
        plugin.invalidate_config_cache()  # a worker must see what the web saved
    except Exception:  # noqa: BLE001
        logger.debug('aliexpress: config cache not invalidated', exc_info=True)
    return plugin.get_config() or {}


def app_credentials() -> tuple[str, str]:
    cfg = config()
    return str(cfg.get('app_key') or '').strip(), str(cfg.get('app_secret') or '').strip()


def sign(secret: str, params: dict, api_path: str = '') -> str:
    """The IOP signature: HMAC-SHA256 over [path] + sorted key+value pairs, upper hex."""
    base = api_path + ''.join(f'{k}{params[k]}' for k in sorted(params) if str(params[k]).strip())
    return (
        hmac.new(secret.encode('utf-8'), base.encode('utf-8'), hashlib.sha256).hexdigest().upper()
    )


def _value(v) -> str:
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (dict, list)):
        return json.dumps(v, separators=(',', ':'), ensure_ascii=False)
    return str(v)


def unwrap(node: Any) -> Any:
    """Strip ``<method>_response`` and single-key list wrappers, recursively."""
    if isinstance(node, list):
        return [unwrap(item) for item in node]
    if not isinstance(node, dict):
        return node
    if len(node) == 1:
        ((key, value),) = node.items()
        if key.endswith('_response') and isinstance(value, dict):
            return unwrap(value)
        if isinstance(value, list) and key not in ('result', 'data'):
            return unwrap(value)
    return {k: unwrap(v) for k, v in node.items()}


def _post(url: str, data: dict) -> dict:
    import requests  # noqa: PLC0415

    try:
        resp = requests.post(url, data=data, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise AEError(f'AliExpress is unreachable: {e}') from e
    try:
        body = resp.json()
    except ValueError as e:
        raise AEError(f'AliExpress answered HTTP {resp.status_code} without JSON.') from e
    if isinstance(body, dict) and 'error_response' in body:
        err = body['error_response'] or {}
        raise AEError(
            str(err.get('sub_msg') or err.get('msg') or 'AliExpress refused the call'),
            str(err.get('sub_code') or err.get('code') or ''),
        )
    if resp.status_code != 200:  # noqa: PLR2004
        raise AEError(f'AliExpress answered HTTP {resp.status_code}.')
    return body if isinstance(body, dict) else {}


def _system(api_path: str, params: dict) -> dict:
    key, secret = app_credentials()
    if not key or not secret:
        raise AEError(
            'Add the AliExpress app key and secret under Settings → Shipping → AliExpress.'
        )
    data = {'app_key': key, 'timestamp': str(int(time.time() * 1000)), 'sign_method': 'sha256'}
    data.update({k: _value(v) for k, v in params.items() if v not in (None, '')})
    data['sign'] = sign(secret, data, api_path)
    return _post(f'{GATEWAY}/rest{api_path}', data)


def _store_tokens(body: dict) -> dict:
    plugin = _plugin()
    tokens = {
        '_access_token': body.get('access_token') or '',
        '_refresh_token': body.get('refresh_token') or '',
        '_access_expires_ms': int(body.get('expire_time') or 0),
        '_refresh_expires_ms': int(body.get('refresh_token_valid_time') or 0),
        '_account': str(body.get('account') or body.get('user_nick') or ''),
    }
    if not tokens['_access_token']:
        raise AEError('AliExpress returned no access token.')
    for k, v in tokens.items():
        plugin.set_config(k, v)
    return tokens


def exchange_code(code: str) -> dict:
    """OAuth step 2: the code from the callback → tokens, stored."""
    return _store_tokens(_system('/auth/token/create', {'code': code}))


def refresh_tokens() -> dict:
    refresh = str(config().get('_refresh_token') or '')
    if not refresh:
        raise AEError('AliExpress is not connected — connect the account on the AliExpress page.')
    return _store_tokens(_system('/auth/token/refresh', {'refresh_token': refresh}))


def connection() -> dict:
    cfg = config()
    return {
        'connected': bool(cfg.get('_access_token')),
        'account': cfg.get('_account') or '',
        'access_expires_ms': int(cfg.get('_access_expires_ms') or 0),
        'refresh_expires_ms': int(cfg.get('_refresh_expires_ms') or 0),
    }


def disconnect() -> None:
    plugin = _plugin()
    for k in (
        '_access_token',
        '_refresh_token',
        '_access_expires_ms',
        '_refresh_expires_ms',
        '_account',
    ):
        plugin.set_config(k, '' if not k.endswith('_ms') else 0)


def access_token() -> str:
    cfg = config()
    token = str(cfg.get('_access_token') or '')
    if not token:
        raise AEError('AliExpress is not connected — connect the account on the AliExpress page.')
    expires = int(cfg.get('_access_expires_ms') or 0)
    if expires and expires - int(time.time() * 1000) < REFRESH_MARGIN_MS:
        token = refresh_tokens()['_access_token']
    return token


def call(method: str, params: dict | None = None, *, token: bool = True) -> dict:
    """Call business ``method``; returns the unwrapped payload."""
    key, secret = app_credentials()
    if not key or not secret:
        raise AEError(
            'Add the AliExpress app key and secret under Settings → Shipping → AliExpress.'
        )
    data = {
        'app_key': key,
        'method': method,
        'timestamp': str(int(time.time() * 1000)),
        'sign_method': 'sha256',
        'format': 'json',
    }
    if token:
        data['access_token'] = access_token()
    data.update({k: _value(v) for k, v in (params or {}).items() if v not in (None, '')})
    data['sign'] = sign(secret, data)
    return unwrap(_post(f'{GATEWAY}/sync', data))

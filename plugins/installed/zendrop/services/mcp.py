"""A small MCP client for Zendrop's server (``https://app.zendrop.com/mcp/v1``).

Zendrop publishes no REST API for stores it does not connect to natively, but
its MCP server is a standards-compliant one: JSON-RPC 2.0 over HTTP POST,
``Authorization: Bearer <access token>``, OAuth resource metadata at
``/.well-known/oauth-protected-resource/mcp/v1``, scopes such as
``orders:read`` / ``orders:write`` / ``catalog:read``. The tool names are only
visible to an authenticated client, so this module's job is discovery: connect,
list the tools the merchant's token can reach, and show them. Nothing here
writes to Zendrop.

The token never appears in a log line or an error message.
"""

from __future__ import annotations

import contextlib
import json
import logging
import re

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('morpheus.zendrop')

MCP_URL = 'https://app.zendrop.com/mcp/v1'
PROTOCOL_VERSION = '2025-06-18'
SNAPSHOT_KEY = 'zendrop:connection:v1'
SNAPSHOT_TTL = 60 * 60
TIMEOUT = 20

# What a tool name lets a merchant do. Heuristic by design: the names are
# Zendrop's and may change; the page shows the raw list beside this grouping.
CAPABILITY_KEYS = ('orders_read', 'orders_write', 'shipping', 'catalog')
_READ_WORDS = ('list', 'get', 'status', 'search', 'detail', 'fetch', 'find')
_WRITE_WORDS = ('create', 'update', 'cancel', 'submit', 'place')


def _classify(name: str) -> list[str]:
    n = re.sub(r'[^a-z]', '', name.lower())
    out = []
    if 'track' in n or ('order' in n and any(w in n for w in _READ_WORDS)):
        out.append('orders_read')
    if 'fulfil' in n or 'address' in n or ('order' in n and any(w in n for w in _WRITE_WORDS)):
        out.append('orders_write')
    if any(w in n for w in ('shipping', 'estimate', 'quote', 'delivery')):
        out.append('shipping')
    if any(w in n for w in ('catalog', 'product')):
        out.append('catalog')
    return out


class McpError(RuntimeError):
    """Zendrop could not be reached or refused the call (message is token-free)."""


def access_token() -> str:
    from plugins.registry import app_registry

    plugin = app_registry.get('zendrop')
    cfg = plugin.get_config() if plugin is not None else {}
    return str(cfg.get('access_token') or '').strip()


def _post(payload: dict, token: str, session_id: str | None = None):
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream',
        'MCP-Protocol-Version': PROTOCOL_VERSION,
    }
    if session_id:
        headers['Mcp-Session-Id'] = session_id
    try:
        return requests.post(MCP_URL, json=payload, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as exc:  # no URL params, so no token to leak
        raise McpError(f'Could not reach Zendrop: {type(exc).__name__}.') from None


def _parse(resp) -> dict:
    """The JSON-RPC envelope from a JSON body or an SSE stream (``data:`` lines)."""
    content_type = (resp.headers.get('Content-Type') or '').lower()
    if 'text/event-stream' in content_type:
        for line in (resp.text or '').splitlines():
            if line.startswith('data:'):
                data = json.loads(line[5:].strip() or '{}')
                if 'result' in data or 'error' in data:
                    return data
        raise McpError('Zendrop sent an empty event stream.')
    try:
        return resp.json()
    except ValueError:
        raise McpError('Zendrop answered with something that is not JSON.') from None


def rpc(method: str, params: dict | None = None, *, token: str, session_id: str | None = None):
    """One JSON-RPC call. Returns ``(result, session_id)``."""
    resp = _post(
        {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}}, token, session_id
    )
    if resp.status_code == 401:
        raise McpError('Zendrop rejected the access token (401). Generate a new one in Zendrop.')
    if resp.status_code == 403:
        raise McpError("Zendrop refused (403): the token's scopes do not allow this.")
    if resp.status_code >= 400:
        raise McpError(f'Zendrop answered HTTP {resp.status_code} to {method}.')
    data = _parse(resp)
    if 'error' in data:
        message = data['error'].get('message') if isinstance(data['error'], dict) else data['error']
        raise McpError(f'{method}: {str(message)[:200]}')
    return data.get('result') or {}, resp.headers.get('Mcp-Session-Id') or session_id


def list_tools(token: str) -> dict:
    """``initialize`` + ``tools/list``: the server's identity and its tool catalogue."""
    init, session_id = rpc(
        'initialize',
        {
            'protocolVersion': PROTOCOL_VERSION,
            'capabilities': {},
            'clientInfo': {'name': 'morpheus', 'version': settings.MORPHEUS_VERSION},
        },
        token=token,
    )
    # A notification: no id, no reply expected; failure to deliver it is not an error.
    with contextlib.suppress(McpError):
        _post({'jsonrpc': '2.0', 'method': 'notifications/initialized'}, token, session_id)
    tools, _ = rpc('tools/list', token=token, session_id=session_id)
    return {
        'server': (init.get('serverInfo') or {}),
        'protocol': init.get('protocolVersion') or '',
        'tools': [
            {'name': str(t.get('name') or ''), 'description': str(t.get('description') or '')[:200]}
            for t in (tools.get('tools') or [])
        ],
    }


def capabilities(tools: list[dict]) -> dict[str, list[str]]:
    """Group tool names by what they let a merchant do (heuristic, see _classify)."""
    out: dict[str, list[str]] = {key: [] for key in CAPABILITY_KEYS}
    for tool in tools:
        name = tool.get('name') or ''
        for key in _classify(name):
            if name not in out[key]:
                out[key].append(name)
    return out


def test_connection() -> dict:
    """Connect with the stored token; cache and return a snapshot for the page."""
    token = access_token()
    if not token:
        snapshot = {'ok': False, 'error': 'No access token saved yet.', 'tools': []}
        cache.delete(SNAPSHOT_KEY)
        return snapshot
    try:
        listing = list_tools(token)
        snapshot = {
            'ok': True,
            'error': '',
            **listing,
            'capabilities': capabilities(listing['tools']),
        }
        logger.info('zendrop: connected, %d tools', len(listing['tools']))
    except McpError as exc:
        snapshot = {'ok': False, 'error': str(exc), 'tools': []}
        logger.warning('zendrop: connection test failed: %s', exc)
    cache.set(SNAPSHOT_KEY, snapshot, SNAPSHOT_TTL)
    return snapshot


def cached_connection() -> dict | None:
    return cache.get(SNAPSHOT_KEY)

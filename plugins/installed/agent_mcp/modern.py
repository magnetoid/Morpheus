"""MCP 2026-07-28: the stateless, per-request era of the protocol.

Since 2026-07-28 there is no ``initialize`` handshake and no session: every
request names its protocol version and client capabilities in ``params._meta``
and mirrors ``method`` / ``params.name`` into the ``Mcp-Method`` / ``Mcp-Name``
headers so intermediaries can route without parsing the body. The server
validates the mirror (``-32020`` HeaderMismatch), refuses versions it does not
speak (``-32022``, listing the ones it does), answers ``server/discover``,
stamps every result with ``resultType`` + its own identity, and marks list
and read results cacheable (``ttlMs`` + ``cacheScope``).

``views.rpc_endpoint`` is a *dual-era* server: a request that carries the
modern ``_meta`` (or a modern version header) is served statelessly through
the helpers here; a request that opens with ``initialize`` is served with the
legacy semantics exactly as before. The two eras share the handlers, the
auth/scope stash, the audit trail and the rate limits — only the envelope
differs. Digest of the spec pages this follows:
``changelog``, ``basic/versioning``, ``basic/index`` (``_meta``, error codes),
``server/discover``, ``basic/transports/streamable-http``.
"""

from __future__ import annotations

import base64
import binascii
from typing import Any
from urllib.parse import urlsplit

MODERN_VERSIONS = ('2026-07-28',)
LEGACY_VERSIONS = ('2024-11-05',)
SUPPORTED_VERSIONS = MODERN_VERSIONS + LEGACY_VERSIONS

META_VERSION = 'io.modelcontextprotocol/protocolVersion'
META_CLIENT_CAPABILITIES = 'io.modelcontextprotocol/clientCapabilities'
META_CLIENT_INFO = 'io.modelcontextprotocol/clientInfo'
META_SERVER_INFO = 'io.modelcontextprotocol/serverInfo'

# Error codes the specification reserves (-32020 … -32099).
E_HEADER_MISMATCH = -32020
E_MISSING_CLIENT_CAPABILITY = -32021
E_UNSUPPORTED_VERSION = -32022
# Application errors of this server in the modern era. The legacy sub-range
# (-32000 … -32019) is discouraged for new use and -32002 may not be emitted
# at all, so these live outside the JSON-RPC reserved range altogether.
E_AUTH_REQUIRED = 40100
E_APPROVAL_REQUIRED = 40300
E_RATE_LIMITED = 42900

# Methods that mirror a name into Mcp-Name, and where that name lives.
_NAMED = {'tools/call': 'name', 'resources/read': 'uri', 'prompts/get': 'name'}

# ttlMs / cacheScope per cacheable method (CacheableResult). A list that
# depends on the caller's token is private; the anonymous view is public.
_CACHEABLE = {
    'server/discover': (3_600_000, 'public'),
    'tools/list': (300_000, None),
    'resources/list': (300_000, None),
    'resources/read': (60_000, 'private'),
    'resources/templates/list': (300_000, 'public'),
    'prompts/list': (300_000, 'public'),
}

_SENTINEL_PREFIX, _SENTINEL_SUFFIX = '=?base64?', '?='


class ModernError(Exception):
    """A validation failure with the JSON-RPC code and HTTP status to send."""

    def __init__(self, code: int, message: str, *, status: int = 400, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.data = data


def is_modern(request, body) -> bool:
    """A request is served statelessly when it carries the per-request
    ``_meta`` version, or a version header from the modern era. A legacy
    client sends neither (2024-11-05 … 2025-03-26) or a legacy header
    (2025-06-18 … 2025-11-25)."""
    header = (request.headers.get('MCP-Protocol-Version') or '').strip()
    if header and header >= MODERN_VERSIONS[0]:
        return True
    if isinstance(body, dict):
        params = body.get('params')
        meta = params.get('_meta') if isinstance(params, dict) else None
        if isinstance(meta, dict) and meta.get(META_VERSION):
            return True
    return False


def foreign_origin(request) -> bool:
    """True when a browser-style ``Origin`` names another site: the transport
    requires validating it against DNS rebinding. Agents send no Origin."""
    origin = request.headers.get('Origin')
    if origin is None:
        return False
    try:
        host = (urlsplit(origin).netloc or '').lower()
        return host != request.get_host().lower()
    except Exception:  # noqa: BLE001 — an unparsable Origin is foreign
        return True


def decode_name(value: str) -> str:
    """``Mcp-Name`` / ``Mcp-Param-*`` values may carry the Base64 sentinel."""
    value = value.strip()
    if value.startswith(_SENTINEL_PREFIX) and value.endswith(_SENTINEL_SUFFIX):
        inner = value[len(_SENTINEL_PREFIX) : -len(_SENTINEL_SUFFIX)]
        try:
            return base64.b64decode(inner, validate=True).decode('utf-8')
        except (binascii.Error, ValueError) as e:
            raise ModernError(E_HEADER_MISMATCH, 'Mcp-Name is not valid Base64') from e
    return value


def validate(request, body) -> dict:
    """Check the modern envelope; return ``{'version', 'method', 'params'}``.

    Order matters for the client's fallback logic: a body that is not one
    request is ``-32600``; a missing ``_meta`` field is ``-32602``; a header
    that disagrees with the body is ``-32020``; a version we do not speak is
    ``-32022`` with the supported list — every one of them HTTP 400 with a
    JSON-RPC body, which is how a dual-era client tells us from a server that
    only speaks the handshake.
    """
    method, params, version = _validate_body(body)
    _validate_headers(request, method, params, version)
    return {'version': version, 'method': method, 'params': params}


def _validate_body(body) -> tuple[str, dict, str]:
    if not isinstance(body, dict):
        raise ModernError(-32600, 'the body must be a single JSON-RPC request or notification')
    method = body.get('method')
    if not isinstance(method, str) or not method:
        raise ModernError(-32600, 'method must be a string')
    params = body.get('params') or {}
    if not isinstance(params, dict):
        raise ModernError(-32602, 'params must be an object')
    meta = params.get('_meta')
    if not isinstance(meta, dict):
        raise ModernError(-32602, f'params._meta with {META_VERSION} is required')
    version = meta.get(META_VERSION)
    if not isinstance(version, str) or not version:
        raise ModernError(-32602, f'params._meta.{META_VERSION} is required')
    if not isinstance(meta.get(META_CLIENT_CAPABILITIES), dict):
        raise ModernError(-32602, f'params._meta.{META_CLIENT_CAPABILITIES} is required')
    return method, params, version


def _validate_headers(request, method: str, params: dict, version: str) -> None:
    header_version = (request.headers.get('MCP-Protocol-Version') or '').strip()
    if not header_version:
        raise ModernError(E_HEADER_MISMATCH, 'MCP-Protocol-Version header is required')
    if header_version != version:
        raise ModernError(
            E_HEADER_MISMATCH,
            f'MCP-Protocol-Version header {header_version!r} does not match '
            f'params._meta value {version!r}',
        )
    if version not in MODERN_VERSIONS:
        raise ModernError(
            E_UNSUPPORTED_VERSION,
            'Unsupported protocol version',
            data={'supported': list(SUPPORTED_VERSIONS), 'requested': version},
        )
    header_method = (request.headers.get('Mcp-Method') or '').strip()
    if not header_method:
        raise ModernError(E_HEADER_MISMATCH, 'Mcp-Method header is required')
    if header_method != method:
        raise ModernError(
            E_HEADER_MISMATCH,
            f'Mcp-Method header {header_method!r} does not match body method {method!r}',
        )
    field = _NAMED.get(method)
    if field is None:
        return
    raw = request.headers.get('Mcp-Name')
    if raw is None:
        raise ModernError(E_HEADER_MISMATCH, f'Mcp-Name header is required for {method}')
    if decode_name(raw) != str(params.get(field) or ''):
        raise ModernError(E_HEADER_MISMATCH, f'Mcp-Name header does not match params.{field}')


def server_info() -> dict:
    from django.conf import settings  # noqa: PLC0415

    from core.utils.site import store_slug  # noqa: PLC0415

    return {
        'name': store_slug('mcp'),
        'version': str(getattr(settings, 'MORPHEUS_VERSION', '') or '0.1.0'),
    }


def discover_result(*, authed: bool) -> dict:
    """``server/discover``: versions, capabilities and identity, cacheable."""
    from core.utils.site import store_name  # noqa: PLC0415

    return decorate(
        {
            'supportedVersions': list(SUPPORTED_VERSIONS),
            'capabilities': {
                'tools': {'listChanged': False},
                'resources': {'listChanged': False, 'subscribe': False},
            },
            'instructions': (
                f'{store_name()} commerce server. `tools/list` names the read tools '
                '(and, with a Bearer token, the writes its scopes allow); '
                '`tools/call` runs one. Without a token the catalogue is '
                'discoverable but not callable.'
            ),
            'authenticated': authed,
        },
        'server/discover',
        authed=authed,
    )


def decorate(result: dict, method: str, *, authed: bool) -> dict:
    """Stamp a result with ``resultType``, the server identity and, for the
    cacheable methods, ``ttlMs`` + ``cacheScope``."""
    out = dict(result)
    out.setdefault('resultType', 'complete')
    meta = dict(out.get('_meta') or {})
    meta.setdefault(META_SERVER_INFO, server_info())
    out['_meta'] = meta
    cacheable = _CACHEABLE.get(method)
    if cacheable:
        ttl, scope = cacheable
        out.setdefault('ttlMs', ttl)
        out.setdefault('cacheScope', scope or ('private' if authed else 'public'))
    return out


def translate_error(code: int) -> int:
    """Map the legacy-era application codes onto the modern ones."""
    return {-32001: E_AUTH_REQUIRED, -32030: E_APPROVAL_REQUIRED, -32029: E_RATE_LIMITED}.get(
        code, code
    )


def http_status(code: int, *, method_found: bool = True) -> int:
    if not method_found:
        return 404
    if code in (
        -32600,
        -32602,
        E_HEADER_MISMATCH,
        E_MISSING_CLIENT_CAPABILITY,
        E_UNSUPPORTED_VERSION,
    ):
        return 400
    return 200

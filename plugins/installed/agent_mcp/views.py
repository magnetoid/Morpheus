"""MCP server — JSON-RPC 2.0 endpoint for external AI agents.

Implements a useful subset of the Model Context Protocol:
  * initialize       — handshake, returns server capabilities
  * tools/list       — list every tool the caller's API key can invoke
  * tools/call       — dispatch a single tool with args, return result
  * resources/list   — list discoverable resources (= top-level catalog
                       summaries, e.g. featured products)
  * resources/read   — read one resource (deep-fetch a product/order)
  * ping             — liveness check (returns {})

Anything else returns a JSON-RPC -32601 (Method not found).

Auth: `Authorization: Bearer <api_key>` mapped against the store's
PluginConfig['agent_mcp']['public_keys'] list. Callers without a
valid key still get `initialize` and a redacted `tools/list` (only
the name + description, not callable). This lets agents discover the
shape of the API before negotiating a key.

Tools exposed: a curated subset of the Assistant's read tools — the
ones a public AI agent should be able to call to drive a shopper
toward checkout. Write tools and admin-only reads (settings.list,
fs.*, logs.*, plugins.*) are NEVER reachable here.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger('morpheus.agent_mcp')

# ── JSON-RPC error codes ──────────────────────────────────────────────
_E_PARSE = -32700
_E_INVALID = -32600
_E_METHOD = -32601
_E_PARAMS = -32602
_E_INTERNAL = -32603
_E_AUTH = -32001  # custom: needs auth
_E_TOOL_FAIL = -32002  # custom: tool errored


# ── Curated tool whitelist ─────────────────────────────────────────────
# Only the read tools that are safe for an external public AI agent to
# call go here. Admin/system reads + writes are excluded entirely.
_PUBLIC_TOOL_NAMES = {
    'orders.search', 'orders.get',
    'products.search', 'products.get',
    'customers.search', 'customers.get',
    'analytics.summary', 'analytics.top_products',
    'cms.pages',
    'db.describe_model', 'db.count_rows', 'db.list_models',
    # Linda's memory layer is read-safe — external agents can recall the
    # store's stable preferences (e.g. "ships from EU"). Writes
    # (memory.remember / memory.forget) stay internal to Linda.
    'memory.recall',
}


def _public_tools() -> list:
    """Resolve the curated tool whitelist into actual tool objects.

    Three modes:
      * Cluster server with explicit names → exact-name filter on the
        full Linda tool catalog. Used by storefront/cart/checkout.
      * Cluster server set to "all" → no filter; admin sees everything.
      * No cluster active (legacy ``/mcp/v1/``) → filter by the
        backward-compatible ``_PUBLIC_TOOL_NAMES`` set.
    """
    try:
        from core.assistant.tools import get_default_tools
    except Exception as e:  # noqa: BLE001
        logger.warning('agent_mcp: tool resolution failed: %s', e)
        return []
    all_tools = get_default_tools()
    try:
        from plugins.installed.agent_mcp.servers import active_cluster
        cluster = active_cluster()
        if cluster is not None:
            names = cluster.get('names')
            if names is None:  # admin — all tools
                return all_tools
            return [t for t in all_tools if t.name in names]
    except Exception:  # noqa: BLE001
        pass
    return [t for t in all_tools if t.name in _PUBLIC_TOOL_NAMES]


def _api_keys() -> set[str]:
    """Active API keys from PluginConfig['agent_mcp']['public_keys'].

    Each entry is either a raw string (legacy) or a dict with at least a
    `token` field. The dict form lets the dashboard token manager label
    + track tokens for ops; the string form keeps existing integrations
    working unchanged.
    """
    try:
        from plugins.models import PluginConfig
        cfg = PluginConfig.objects.filter(plugin_name='agent_mcp').first()
        if cfg is None:
            return set()
        keys = (cfg.config or {}).get('public_keys') or []
        out: set[str] = set()
        for k in keys:
            if isinstance(k, dict):
                tok = (k.get('token') or '').strip()
            else:
                tok = str(k).strip()
            if tok:
                out.add(tok)
        return out
    except Exception as e:  # noqa: BLE001
        logger.warning('agent_mcp: api-key lookup failed: %s', e)
        return set()


def _is_authed(request: HttpRequest) -> bool:
    auth = request.headers.get('Authorization', '')
    if not auth.lower().startswith('bearer '):
        return False
    presented = auth.split(' ', 1)[1].strip()
    return presented in _api_keys() if presented else False


# ── Handlers ───────────────────────────────────────────────────────────


def _handle_initialize(params: dict, authed: bool) -> dict:
    return {
        'protocolVersion': '2024-11-05',
        'capabilities': {
            'tools': {'listChanged': False},
            'resources': {'listChanged': False, 'subscribe': False},
        },
        'serverInfo': {
            'name': 'morpheus-mcp',
            'version': '0.1.0',
        },
        'authenticated': authed,
        'instructions': (
            'Morpheus catalog API. Use `tools/list` to see available '
            'read tools, then `tools/call` to fetch products, orders, '
            'and analytics. Public access without an API key is '
            'limited to discovery; passing a Bearer token enables '
            'tool calls.'
        ),
    }


def _handle_tools_list(params: dict, authed: bool) -> dict:
    tools = _public_tools()
    out = []
    for t in tools:
        entry = {
            'name': t.name,
            'description': getattr(t, 'description', ''),
            'inputSchema': getattr(t, 'schema', None) or {'type': 'object', 'properties': {}},
        }
        if not authed:
            # Drop the schema for unauthenticated discovery — they can
            # see what exists but not how to call it. Re-issue with a key.
            entry['inputSchema'] = {'type': 'object', 'properties': {}}
            entry['_auth_required'] = True
        out.append(entry)
    return {'tools': out}


def _handle_tools_call(params: dict, authed: bool) -> dict:
    if not authed:
        raise _RpcError(_E_AUTH, 'authentication required for tools/call')
    name = (params or {}).get('name', '')
    args = (params or {}).get('arguments', {}) or {}
    if not name:
        raise _RpcError(_E_PARAMS, 'missing `name`')
    if name not in _PUBLIC_TOOL_NAMES:
        raise _RpcError(_E_METHOD, f'tool not exposed: {name}')

    tool = next((t for t in _public_tools() if t.name == name), None)
    if tool is None:
        raise _RpcError(_E_METHOD, f'tool not found: {name}')

    # Scope enforcement. The presented token's `mcp_scopes` were stashed
    # on a thread-local during rpc_endpoint(); legacy / wildcard tokens
    # always pass. Tools without declared scopes are treated as public
    # (anyone authed can call them — e.g. read-only diagnostics).
    from plugins.installed.agent_mcp.scopes import has_any
    granted = _active_token_scopes()
    required = list(getattr(tool, 'scopes', None) or [])
    if not has_any(granted, required):
        raise _RpcError(
            _E_AUTH,
            f'token missing scope: needs one of {required}',
        )

    # OpenTelemetry span wrap — agent traffic now shows in the same
    # APM dashboards as human requests, attributed by tool name +
    # token scopes. Silent no-op when OTel isn't installed so the MCP
    # surface stays working in plain installs.
    try:
        from opentelemetry import trace
        tracer = trace.get_tracer('morpheus.mcp')
        _span_ctx = tracer.start_as_current_span(
            f'mcp.tools.call.{name}',
            attributes={
                'mcp.tool_name': name,
                'mcp.granted_scopes': ','.join(sorted(granted)) or '(legacy)',
                'mcp.arg_count': len(args),
            },
        )
    except Exception:  # noqa: BLE001 — OTel optional
        from contextlib import nullcontext
        _span_ctx = nullcontext()

    with _span_ctx:
        try:
            result = tool.invoke(args, agent=None, context={'source': 'mcp'})
            output = result.output if hasattr(result, 'output') else result
        except Exception as e:  # noqa: BLE001 — surface as JSON-RPC error
            raise _RpcError(_E_TOOL_FAIL, f'{type(e).__name__}: {e}') from e

    # MCP tools/call returns content blocks; we wrap the structured
    # output as a single JSON text block so MCP clients can consume it
    # uniformly.
    return {
        'content': [
            {'type': 'text', 'text': json.dumps(output, default=str)},
        ],
        'isError': False,
    }


def _handle_resources_list(params: dict, authed: bool) -> dict:
    """Surface a small set of useful entry-point resources.

    Each resource has a `uri` an MCP client can pass to `resources/read`
    to fetch the underlying data. We model:
      * morpheus://catalog/featured — featured products
      * morpheus://catalog/recent   — newest products
      * morpheus://analytics/today  — today's revenue + orders
    """
    return {
        'resources': [
            {
                'uri': 'morpheus://catalog/featured',
                'name': 'Featured products',
                'description': 'The curated featured product list.',
                'mimeType': 'application/json',
            },
            {
                'uri': 'morpheus://catalog/recent',
                'name': 'Recent products',
                'description': 'Newest 20 products in the catalog.',
                'mimeType': 'application/json',
            },
            {
                'uri': 'morpheus://analytics/today',
                'name': "Today's analytics summary",
                'description': 'Orders + revenue for the current day.',
                'mimeType': 'application/json',
            },
        ],
    }


def _handle_resources_read(params: dict, authed: bool) -> dict:
    if not authed:
        raise _RpcError(_E_AUTH, 'authentication required for resources/read')
    uri = (params or {}).get('uri', '')
    if not uri.startswith('morpheus://'):
        raise _RpcError(_E_PARAMS, f'unknown uri: {uri}')

    tools = {t.name: t for t in _public_tools()}
    try:
        if uri == 'morpheus://catalog/featured':
            t = tools.get('products.search')
            if t is None:
                raise _RpcError(_E_INTERNAL, 'products.search unavailable')
            data = t.invoke({'status': 'active', 'limit': 20},
                            agent=None, context={'source': 'mcp'}).output
        elif uri == 'morpheus://catalog/recent':
            t = tools.get('products.search')
            data = t.invoke({'limit': 20}, agent=None, context={'source': 'mcp'}).output
        elif uri == 'morpheus://analytics/today':
            t = tools.get('analytics.summary')
            data = t.invoke({'days_back': 1}, agent=None, context={'source': 'mcp'}).output
        else:
            raise _RpcError(_E_PARAMS, f'unknown uri: {uri}')
    except _RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise _RpcError(_E_TOOL_FAIL, f'{type(e).__name__}: {e}') from e

    return {
        'contents': [
            {
                'uri': uri,
                'mimeType': 'application/json',
                'text': json.dumps(data, default=str),
            },
        ],
    }


_HANDLERS = {
    'initialize': _handle_initialize,
    'tools/list': _handle_tools_list,
    'tools/call': _handle_tools_call,
    'resources/list': _handle_resources_list,
    'resources/read': _handle_resources_read,
    'ping': lambda params, authed: {},
}


class _RpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


# ── HTTP entry point ───────────────────────────────────────────────────


import threading
_request_state = threading.local()


def _active_token_scopes() -> set[str]:
    """Token scopes for the in-flight request — populated by
    rpc_endpoint() before dispatch. Falls back to the wildcard so
    sessions-authed staff (no token) keep working."""
    from plugins.installed.agent_mcp.scopes import WILDCARD
    return getattr(_request_state, 'scopes', {WILDCARD})


@csrf_exempt
@require_http_methods(['POST', 'GET'])
def rpc_endpoint(request: HttpRequest) -> HttpResponse:
    """Single JSON-RPC 2.0 entry point.

    Implements the MCP Streamable HTTP transport (2025-03-26+):
      * POST with Accept: application/json → standard JSON response
      * POST with Accept: text/event-stream → SSE-wrapped JSON-RPC payload
      * GET → 405 (no server-initiated streams; we're request/response only)
      * Mcp-Session-Id is minted on initialize and echoed by the client
        on subsequent calls.
    """
    if request.method == 'GET':
        # Server-initiated SSE streams aren't supported; per the spec the
        # server MAY return 405 when it has no notifications to push.
        return HttpResponse(status=405)

    try:
        body = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse(_error_envelope(None, _E_PARSE, 'parse error'), status=400)

    authed = _is_authed(request)
    # Resolve Bearer → user + stash scopes for the in-flight handler.
    # Doing this here covers callers that hit rpc_endpoint directly
    # (legacy /mcp/v1/) without going through the cluster wrappers.
    from plugins.installed.agent_mcp.auth import apply_bearer_user
    apply_bearer_user(request)
    from plugins.installed.agent_mcp.scopes import WILDCARD
    _request_state.scopes = getattr(
        request, '_morph_token_scopes_mcp', {WILDCARD},
    )
    try:
        if isinstance(body, list):
            payload: Any = [_dispatch(m, authed) for m in body]
            had_init = any(
                isinstance(m, dict) and m.get('method') == 'initialize'
                for m in body
            )
        else:
            payload = _dispatch(body, authed)
            had_init = isinstance(body, dict) and body.get('method') == 'initialize'

        session_id = request.headers.get('Mcp-Session-Id') or (
            uuid.uuid4().hex if had_init else ''
        )

        if 'text/event-stream' in request.headers.get('Accept', '').lower():
            sse = f'data: {json.dumps(payload, default=str)}\n\n'
            resp: HttpResponse = HttpResponse(sse, content_type='text/event-stream')
        else:
            resp = JsonResponse(payload, safe=False)

        if session_id:
            resp['Mcp-Session-Id'] = session_id
        return resp
    finally:
        _request_state.scopes = {WILDCARD}


def _dispatch(message: dict, authed: bool) -> dict:
    if not isinstance(message, dict):
        return _error_envelope(None, _E_INVALID, 'message must be an object')
    method = message.get('method')
    msg_id = message.get('id')
    params = message.get('params') or {}
    handler = _HANDLERS.get(method)
    if handler is None:
        return _error_envelope(msg_id, _E_METHOD, f'method not found: {method}')
    try:
        result = handler(params, authed)
    except _RpcError as e:
        return _error_envelope(msg_id, e.code, e.message, e.data)
    except Exception as e:  # noqa: BLE001 — last-resort safety
        logger.error('agent_mcp: handler crashed on %s: %s', method, e, exc_info=True)
        return _error_envelope(msg_id, _E_INTERNAL, f'internal error: {e}')
    if msg_id is None:
        # Notification — no response per JSON-RPC spec.
        return {}
    return {'jsonrpc': '2.0', 'id': msg_id, 'result': result}


def _error_envelope(msg_id: Any, code: int, message: str, data: Any = None) -> dict:
    err: dict[str, Any] = {'code': code, 'message': message}
    if data is not None:
        err['data'] = data
    return {'jsonrpc': '2.0', 'id': msg_id, 'error': err}


# ── Auxiliary endpoints ────────────────────────────────────────────────


@require_http_methods(['GET'])
def health(request: HttpRequest) -> HttpResponse:
    """Liveness probe — useful for AI clients that want to verify the
    server is reachable before negotiating a JSON-RPC session."""
    return JsonResponse({
        'status': 'ok',
        'name': 'morpheus-mcp',
        'version': '0.1.0',
        'tools_exposed': len(_public_tools()),
    })


@require_http_methods(['GET'])
def manifest(request: HttpRequest) -> HttpResponse:
    """ChatGPT-style plugin manifest. Mounted at /mcp/v1/manifest.json so
    AI clients that prefer the OpenAI plugin discovery shape can find us
    without speaking JSON-RPC first.
    """
    base = request.build_absolute_uri('/').rstrip('/')
    return JsonResponse({
        'schema_version': 'v1',
        'name_for_human': 'Morpheus storefront',
        'name_for_model': 'morpheus_storefront',
        'description_for_human': (
            'Search this store, look up products, fetch order status, '
            'and read recent analytics through a Morpheus-powered '
            'commerce backend.'
        ),
        'description_for_model': (
            'Use this API to answer shopper questions about products, '
            'pricing, stock, and order status. All responses are '
            'authoritative — never hallucinate inventory or prices.'
        ),
        'auth': {
            'type': 'user_http',
            'authorization_type': 'bearer',
        },
        'api': {
            'type': 'jsonrpc',
            'url': f'{base}/mcp/v1/',
        },
        'logo_url': f'{base}/static/admin_dashboard/morpheus-logo.png',
        'contact_email': 'support@morpheus.local',
        'legal_info_url': f'{base}/pages/terms/',
    })

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

import hashlib
import json
import logging
import time
import uuid
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from core.utils.site import store_contact_email, store_logo_url, store_name, store_slug

logger = logging.getLogger('morpheus.agent_mcp')

# ── JSON-RPC error codes ──────────────────────────────────────────────
_E_PARSE = -32700
_E_INVALID = -32600
_E_METHOD = -32601
_E_PARAMS = -32602
_E_INTERNAL = -32603
_E_AUTH = -32001  # custom: needs auth
_E_TOOL_FAIL = -32002  # custom: tool errored
_E_RATE = -32029  # custom: token rate limit exceeded
_E_APPROVAL = -32030  # custom: tool needs a per-token approval grant


# ── Curated tool whitelist ─────────────────────────────────────────────
# Only the read tools that are safe for an external public AI agent to
# call go here. Admin/system reads + writes are excluded entirely.
_PUBLIC_TOOL_NAMES = {
    'orders.search',
    'orders.get',
    'products.search',
    'products.get',
    'customers.search',
    'customers.get',
    'analytics.summary',
    'analytics.top_products',
    'cms.pages',
    'db.describe_model',
    'db.count_rows',
    'db.list_models',
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
            # Resolve each whitelisted name from Linda's catalog first, then fall
            # back to the plugin registry. Buyer-agent cart/checkout tools live
            # in agentic_checkout (registered via contribute_agent_tools) and are
            # deliberately NOT in Linda's operator catalog — this surfaces them to
            # their cluster without polluting Linda's toolset. A disabled owner's
            # tool simply doesn't resolve, so the cluster shrinks disable-safely.
            by_name = {t.name: t for t in all_tools}
            from morpheus.core import agent_registry

            resolved = []
            for n in names:
                t = by_name.get(n) or agent_registry.get_tool(n)
                if t is not None:
                    resolved.append(t)
            return resolved
    except Exception:  # noqa: BLE001, S110
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
            if isinstance(k, dict):  # noqa: SIM108
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
    from core.assistant.turn_identity import is_turn_token

    if is_turn_token(presented):
        # One Linda turn (see linda_turn.py). Never an entry in public_keys.
        from plugins.installed.agent_mcp.linda_turn import turn_for_request

        return turn_for_request(request) is not None
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
            'name': store_slug('mcp'),
            'version': '0.1.0',
        },
        'authenticated': authed,
        'instructions': (
            f'{store_name()} catalog API. Use `tools/list` to see available '
            'read tools, then `tools/call` to fetch products, orders, '
            'and analytics. Public access without an API key is '
            'limited to discovery; passing a Bearer token enables '
            'tool calls.'
        ),
    }


def _handle_tools_list(params: dict, authed: bool) -> dict:
    turn = getattr(_request_state, 'linda_turn', None)
    if turn is not None:
        from plugins.installed.agent_mcp.linda_turn import catalogue

        tools = catalogue(turn)
    else:
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


# ── Governance helpers (enterprise Phase 1) ─────────────────────────────────
# Audit + approval + rate limiting for the Bearer-token tool surface. The
# in-process agent runtime has its own approval_check (core/agents/runtime.py);
# these close the HTTP edge, writing to the CORE audit trail (core/audit).

_MCP_DEFAULT_RATE_PER_MINUTE = 120


def _mcp_actor() -> str:
    """Audit identity for the in-flight call: token label or staff session."""
    if getattr(_request_state, 'token_present', False):
        label = getattr(_request_state, 'token_label', '') or 'unlabeled-token'
        return f'mcp:{label}'
    return 'mcp:staff-session'


def _audit_denied(tool_name: str, reason: str) -> None:
    """Denials are audit events too — refusals were previously unrecorded."""
    try:
        from core.audit.services import record

        record(
            event_type='mcp.tool_denied',
            severity='warning',
            actor=_mcp_actor(),
            target=f'tool/{tool_name}',
            metadata={'reason': reason},
            request_id=getattr(_request_state, 'request_id', ''),
        )
    except Exception as e:  # noqa: BLE001 — audit must never break the call path
        logger.debug('mcp: denied-audit write failed: %s', e)


def _audit_call(tool_name: str, args: dict, output: Any = None, error: str = '', t0=None) -> None:
    """One agents.decision row per executed MCP tool call (EU AI Act art. 12)."""
    try:
        from morpheus.core import record_ai_decision

        blob = json.dumps(args, default=str)
        capped_args = args if len(blob) <= 4000 else {'_truncated': blob[:4000]}
        if error:
            summary = f'error: {error}'[:1000]
        else:
            summary = json.dumps(output, default=str)[:1000] if output is not None else ''
        record_ai_decision(
            agent=_mcp_actor(),
            actor=_mcp_actor(),  # fills actor_label (agent= only lands in metadata)
            tool=tool_name,
            args=capped_args,
            output=summary,
            duration_ms=int((time.monotonic() - t0) * 1000) if t0 is not None else None,
            target=f'tool/{tool_name}',
            request_id=getattr(_request_state, 'request_id', ''),
        )
    except Exception as e:  # noqa: BLE001 — audit must never break the call path
        logger.debug('mcp: call-audit write failed: %s', e)


def _enforce_rate_limit(tool_name: str) -> None:
    """Per-token fixed-window limit on tool execution. Cache-outage = fail-open
    (availability over strictness; the approval gate still protects writes)."""
    limit = getattr(_request_state, 'rate_limit', None) or _MCP_DEFAULT_RATE_PER_MINUTE
    count = None
    try:
        from django.core.cache import cache

        client = getattr(_request_state, 'rl_client', '') or 'anon'
        key = f'mcp:rl:{client}:{int(time.time() // 60)}'
        try:
            count = cache.incr(key)
        except ValueError:  # key missing — first call this window
            cache.set(key, 1, timeout=120)
            count = 1
    except Exception as e:  # noqa: BLE001
        logger.debug('mcp: rate limit fail-open: %s', e)
        return
    if count is not None and count > limit:
        _audit_denied(tool_name, f'rate_limited (>{limit}/min)')
        raise _RpcError(
            _E_RATE,
            f'rate limited: this token may execute {limit} tool calls/minute; retry shortly',
        )


_JSON_TYPES = {
    'string': str,
    'integer': int,
    'number': (int, float),
    'boolean': bool,
    'array': list,
    'object': dict,
}


def _validate_one_arg(name: str, val, spec: dict) -> str:  # noqa: PLR0911
    """Validate a single argument against its property spec. '' when valid."""
    t = spec.get('type')
    py = _JSON_TYPES.get(t)
    if py is not None:
        # bool is a subclass of int — a boolean is not a valid number.
        if t in ('integer', 'number') and isinstance(val, bool):
            return f'argument {name!r} must be {t}'
        if not isinstance(val, py):
            return f'argument {name!r} must be {t}'
    if 'enum' in spec and val not in spec['enum']:
        return f'argument {name!r} must be one of {spec["enum"]}'
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        if 'minimum' in spec and val < spec['minimum']:
            return f'argument {name!r} must be >= {spec["minimum"]}'
        if 'maximum' in spec and val > spec['maximum']:
            return f'argument {name!r} must be <= {spec["maximum"]}'
    if isinstance(val, str):
        if 'minLength' in spec and len(val) < spec['minLength']:
            return f'argument {name!r} is too short'
        if 'maxLength' in spec and len(val) > spec['maxLength']:
            return f'argument {name!r} is too long'
    return ''


def _validate_tool_args(tool, args: dict) -> str:
    """Validate `args` against `tool.schema` (a JSON-Schema subset). Returns an
    error string, or '' when valid. Dependency-free (no jsonschema): required,
    type, enum, minimum/maximum, minLength/maxLength — enough to stop a bad
    value reaching the ORM. Tool.invoke silently DROPS args the handler doesn't
    name, so without this a typo'd/out-of-range arg reads as a default-valued
    success. Unknown-arg rejection is deliberately NOT done (many schemas are
    under-specified; rejecting would break a legitimately-typed call)."""
    schema = getattr(tool, 'schema', None)
    if not isinstance(schema, dict):
        return ''
    for name in schema.get('required') or []:
        if name not in args:
            return f'missing required argument: {name!r}'
    for name, spec in (schema.get('properties') or {}).items():
        if name in args and isinstance(spec, dict):
            err = _validate_one_arg(name, args[name], spec)
            if err:
                return err
    return ''


_DISCOVERY_METHODS = frozenset({'initialize', 'tools/list', 'resources/list', 'ping'})
_MCP_DISCOVERY_RATE_PER_MINUTE = 240


def _enforce_discovery_rate_limit(method: str) -> None:
    """Rate-limit the UNAUTHENTICATED discovery methods (initialize / tools/list
    / resources/list / ping). These ran a DB query on every call with no cap —
    free enumeration of the admin tool inventory and a cheap DB-amplification
    vector. Keyed on the same rl_client bucket (token hash, else client IP);
    fail-open on a cache outage like the tool-call limiter."""
    try:
        from django.core.cache import cache

        client = getattr(_request_state, 'rl_client', '') or 'anon'
        key = f'mcp:disc:{client}:{int(time.time() // 60)}'
        try:
            count = cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=120)
            count = 1
    except Exception as e:  # noqa: BLE001 — availability over strictness
        logger.debug('mcp: discovery rate limit fail-open: %s', e)
        return
    # django-redis with IGNORE_EXCEPTIONS returns None when Redis is down.
    if count is not None and count > _MCP_DISCOVERY_RATE_PER_MINUTE:
        raise _RpcError(
            _E_RATE,
            f'rate limited: {_MCP_DISCOVERY_RATE_PER_MINUTE} discovery calls/minute; retry shortly',
        )


def _exposed_tool(name: str, turn):
    """Resolve a tool the active cluster exposes, or Linda's catalogue for a turn."""
    if turn is not None:
        from plugins.installed.agent_mcp.linda_turn import catalogue

        candidates = catalogue(turn)
    else:
        candidates = _public_tools()
    tool = next((t for t in candidates if t.name == name), None)
    if tool is None:
        raise _RpcError(_E_METHOD, f'tool not exposed: {name}')
    return tool


def _call_for_turn(tool, name: str, args: dict, turn) -> dict:
    """A Linda turn: Linda's scope profile, the mode, and HUMAN consent from the
    conversation decide — never this request's token scopes or approved_tools."""
    from plugins.installed.agent_mcp.linda_turn import call_tool

    _enforce_rate_limit(name)
    arg_error = _validate_tool_args(tool, args)
    if arg_error:
        raise _RpcError(_E_PARAMS, arg_error)
    return call_tool(tool, name, args, turn, audit_call=_audit_call, audit_denied=_audit_denied)


def _handle_tools_call(params: dict, authed: bool) -> dict:
    if not authed:
        raise _RpcError(_E_AUTH, 'authentication required for tools/call')
    name = (params or {}).get('name', '')
    args = (params or {}).get('arguments', {}) or {}
    if not name:
        raise _RpcError(_E_PARAMS, 'missing `name`')

    # Exposure is decided by the ACTIVE CLUSTER's whitelist (same resolution
    # tools/list uses): legacy /mcp/v1/ still resolves to the curated public
    # reads, while /mcp/admin/v1/ resolves to the full catalog. A hardcoded
    # `name not in _PUBLIC_TOOL_NAMES` pre-check here used to reject every
    # admin write BEFORE scope/approval/rate governance could run — the admin
    # server could list Linda's write tools but never execute one.
    turn = getattr(_request_state, 'linda_turn', None)
    tool = _exposed_tool(name, turn)

    # Kill switch parity. The merchant's "pause agents" switch aborts Linda and
    # the Workers (core/agents/runtime.py) but did NOT reach this Bearer path,
    # so a token could still drive writes while the merchant had pulled the
    # cord. Refuse execution of protected (write/destructive) tools when paused;
    # reads and buyer-facing cart/checkout flows stay up (the switch stops
    # autonomous ACTIONS, not shopping).
    protected = getattr(tool, 'requires_approval', False)
    if turn is not None:
        from plugins.installed.agent_mcp.linda_turn import needs_consent

        protected = needs_consent(tool)
    if protected:
        try:
            from core.agents.guardrails import agents_paused

            paused = agents_paused()
        except Exception:  # noqa: BLE001 — guardrail lookup must never 500 the call
            paused = False
        if paused:
            _audit_denied(name, 'agents_paused')
            raise _RpcError(_E_AUTH, 'agents are paused (merchant kill switch)')

    if turn is not None:
        return _call_for_turn(tool, name, args, turn)

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

    # ── Governance (enterprise Phase 1) ──────────────────────────────────
    # 1. Per-token rate limit (fixed 60s window; audited + fail-open on
    #    cache outage). Protects tool execution from runaway/hostile agents.
    _enforce_rate_limit(name)

    # 2. Approval gate at the HTTP edge. `requires_approval` tools are
    #    callable over MCP only when the merchant pre-approved THIS token for
    #    THIS tool (the `approved_tools` grant on the token entry — a human
    #    decision made in the dashboard, itself audited). Staff sessions (no
    #    token) pass: the human holds the same power in the dashboard UI.
    #    In-process agents get the equivalent gate from core/agents/runtime.py
    #    (approval_check); this closes the previously-unguarded Bearer path.
    if (
        getattr(tool, 'requires_approval', False)
        and getattr(_request_state, 'token_present', False)
        and name not in getattr(_request_state, 'approved_tools', set())
    ):
        _audit_denied(name, 'approval_required')
        raise _RpcError(
            _E_APPROVAL,
            f'approval required: `{name}` is a protected write. Grant it to '
            'this token under Dashboard → Settings → Developer → MCP tokens '
            '(approved tools) to enable it.',
        )

    # Argument validation against the tool's declared schema. Tool.invoke drops
    # unknown/typo'd args silently, so an out-of-range or wrong-typed value would
    # otherwise reach the handler (and the ORM) as a default-valued "success".
    arg_error = _validate_tool_args(tool, args)
    if arg_error:
        raise _RpcError(_E_PARAMS, arg_error)

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

    _t0 = time.monotonic()
    with _span_ctx:
        try:
            result = tool.invoke(args, agent=None, context={'source': 'mcp'})
            output = result.output if hasattr(result, 'output') else result
        except Exception as e:  # noqa: BLE001 — surface as JSON-RPC error
            _audit_call(name, args, error=f'{type(e).__name__}: {e}', t0=_t0)
            raise _RpcError(_E_TOOL_FAIL, f'{type(e).__name__}: {e}') from e
    # Every executed MCP tool call lands in the core audit trail — the AI
    # write surface is no longer invisible (enterprise Phase 1).
    _audit_call(name, args, output=output, t0=_t0)

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


# resources/read is a READ ALIAS over the same tools tools/call exposes, so it
# maps each morpheus:// URI to a backing tool + args and MUST run the SAME
# governance (scope + rate limit + audit). Without it, a token scoped to only
# orders.read could read morpheus://analytics/today (analytics.summary) with no
# scope check and leave no audit row — an authz bypass and a hole in the AI-Act
# evidence trail.
_RESOURCE_TOOLS = {
    'morpheus://catalog/featured': ('products.search', {'status': 'active', 'limit': 20}),
    'morpheus://catalog/recent': ('products.search', {'limit': 20}),
    'morpheus://analytics/today': ('analytics.summary', {'days_back': 1}),
}


def _handle_resources_read(params: dict, authed: bool) -> dict:
    if not authed:
        raise _RpcError(_E_AUTH, 'authentication required for resources/read')
    uri = (params or {}).get('uri', '')
    if not uri.startswith('morpheus://'):
        raise _RpcError(_E_PARAMS, f'unknown uri: {uri}')

    mapping = _RESOURCE_TOOLS.get(uri)
    if mapping is None:
        raise _RpcError(_E_PARAMS, f'unknown uri: {uri}')
    tool_name, args = mapping

    tool = next((t for t in _public_tools() if t.name == tool_name), None)
    if tool is None:
        raise _RpcError(_E_INTERNAL, f'{tool_name} unavailable')

    # Resources are reads. resources/read does not run the requires_approval
    # gate tools/call does, so an approval-gated write must never be mapped as a
    # resource. Today _RESOURCE_TOOLS only points at read tools; this guards a
    # future edit that adds a write-capable one.
    if getattr(tool, 'requires_approval', False):
        raise _RpcError(_E_INTERNAL, f'{tool_name} is not a readable resource')

    # Same scope gate as tools/call (wildcard/legacy tokens still pass).
    from plugins.installed.agent_mcp.scopes import has_any

    granted = _active_token_scopes()
    required = list(getattr(tool, 'scopes', None) or [])
    if not has_any(granted, required):
        raise _RpcError(_E_AUTH, f'token missing scope: needs one of {required}')

    _enforce_rate_limit(tool_name)

    _t0 = time.monotonic()
    try:
        data = tool.invoke(args, agent=None, context={'source': 'mcp'}).output
    except Exception as e:  # noqa: BLE001
        _audit_call(tool_name, args, error=f'{type(e).__name__}: {e}', t0=_t0)
        raise _RpcError(_E_TOOL_FAIL, f'{type(e).__name__}: {e}') from e
    _audit_call(tool_name, args, output=data, t0=_t0)

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


import threading  # noqa: E402 — deliberate late import

_request_state = threading.local()


def _active_token_scopes() -> set[str]:
    """Token scopes for the in-flight request — populated by
    rpc_endpoint() before dispatch. Falls back to the wildcard so
    sessions-authed staff (no token) keep working."""
    from plugins.installed.agent_mcp.scopes import WILDCARD

    return getattr(_request_state, 'scopes', {WILDCARD})


def _stash_linda_turn(request: HttpRequest) -> None:
    """Carry a verified Linda turn into the handlers; attribute its audit rows."""
    from plugins.installed.agent_mcp.linda_turn import turn_for_request

    turn = turn_for_request(request)
    _request_state.linda_turn = turn
    if turn is not None:
        _request_state.token_label = f'linda:user-{turn.user.pk}'
        _request_state.approved_tools = set()


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
    # Deny by default: if apply_bearer_user did not stash a scope set (it always
    # does now, even on failure), treat the caller as unscoped rather than
    # wildcard. An authed token with no scopes is handled per-tool below.
    _request_state.scopes = getattr(request, '_morph_token_scopes_mcp', set())
    # Governance context for this call (see _handle_tools_call): who the token
    # is (audit), what it's pre-approved for, and its rate-limit identity —
    # a token-hash bucket when a Bearer token is present, else the client IP.
    from plugins.installed.agent_mcp.auth import _present_token

    _tok = _present_token(request)
    _request_state.token_present = bool(_tok)
    _request_state.token_label = getattr(request, '_morph_token_label', '') or ''
    _request_state.approved_tools = getattr(request, '_morph_token_approved_tools', set())
    _request_state.rate_limit = getattr(request, '_morph_token_rate_limit', None)
    _request_state.request_id = getattr(request, 'request_id', '') or ''
    _stash_linda_turn(request)
    if _tok:
        _request_state.rl_client = f'tok:{hashlib.sha256(_tok.encode()).hexdigest()[:16]}'
    else:
        _ip = request.META.get('HTTP_CF_CONNECTING_IP') or request.META.get('REMOTE_ADDR', 'anon')
        _request_state.rl_client = f'ip:{_ip}'
    try:
        if isinstance(body, list):
            payload: Any = [_dispatch(m, authed) for m in body]
            had_init = any(isinstance(m, dict) and m.get('method') == 'initialize' for m in body)
        else:
            payload = _dispatch(body, authed)
            had_init = isinstance(body, dict) and body.get('method') == 'initialize'

        session_id = request.headers.get('Mcp-Session-Id') or (uuid.uuid4().hex if had_init else '')

        if 'text/event-stream' in request.headers.get('Accept', '').lower():
            sse = f'data: {json.dumps(payload, default=str)}\n\n'
            resp: HttpResponse = HttpResponse(sse, content_type='text/event-stream')
        else:
            resp = JsonResponse(payload, safe=False)

        if session_id:
            resp['Mcp-Session-Id'] = session_id
        return resp
    finally:
        # Reset thread-local state to DENY between requests (worker threads are
        # reused): a stale wildcard here would fail open for the next caller if
        # anything read scopes before apply_bearer_user ran.
        _request_state.scopes = set()
        _request_state.token_present = False
        _request_state.token_label = ''
        _request_state.approved_tools = set()
        _request_state.rate_limit = None
        _request_state.rl_client = ''
        _request_state.request_id = ''
        _request_state.linda_turn = None


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
        # tools/call and resources/read carry their own per-execution limiter;
        # meter the otherwise-unmetered discovery methods here.
        if method in _DISCOVERY_METHODS:
            _enforce_discovery_rate_limit(method)
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
    return JsonResponse(
        {
            'status': 'ok',
            'name': store_slug('mcp'),
            'version': '0.1.0',
            'tools_exposed': len(_public_tools()),
        }
    )


@require_http_methods(['GET'])
def manifest(request: HttpRequest) -> HttpResponse:
    """ChatGPT-style plugin manifest. Mounted at /mcp/v1/manifest.json so
    AI clients that prefer the OpenAI plugin discovery shape can find us
    without speaking JSON-RPC first.
    """
    base = request.build_absolute_uri('/').rstrip('/')
    # The merchant's brand, not the platform's — this manifest is what an AI
    # client shows a shopper. Logo and contact are omitted when unset rather
    # than pointing at a placeholder that 404s.
    brand = store_name()
    logo = store_logo_url()
    contact = store_contact_email()
    return JsonResponse(
        {
            'schema_version': 'v1',
            'name_for_human': brand,
            'name_for_model': store_slug().replace('-', '_'),
            'description_for_human': (
                f'Search {brand}, look up products, fetch order status, and read recent analytics.'
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
            **({'logo_url': logo} if logo else {}),
            **({'contact_email': contact} if contact else {}),
            # /pages/terms/ is a 404; the cms page route is /p/<slug>/.
            'legal_info_url': f'{base}/p/terms/',
        }
    )

"""Linda turn tokens at the MCP edge — the gates a Janus turn passes through.

Linda's engine (Janus) runs in a subprocess and calls the store's tools here,
at ``/mcp/admin/v1/``. An ordinary API token identifies an integration; a turn
token (``core/assistant/turn_identity.py``) identifies ONE turn of ONE staff
member's conversation. That is what lets this edge enforce what the in-process
loop always enforced, using the same code (``core/assistant/gates.py``):

  * Linda's scope profile — never a token's own, possibly wildcard, scopes;
  * the conversation's mode chip, re-resolved against the user on every call;
  * human consent for ``requires_approval`` tools, spent only by the merchant's
    own latest message, sent after the proposal — a standing ``approved_tools``
    grant plays no part;
  * an ``assistant.tool_write`` audit row naming the human, refusals included.

A turn token never authenticates anything else. ``apply_bearer_user`` does not
recognise it, so GraphQL and every other Bearer surface treat it as an invalid
token and deny.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger('morpheus.agent_mcp.linda_turn')

_UNSET = object()


@dataclass(frozen=True, slots=True)
class LindaTurn:
    user: Any
    conversation_key: str
    mode_slug: str
    # Carried from the turn token so each decision row names the model that
    # made the call (informational, never a gate).
    provider: str = ''
    model: str = ''


def turn_for_request(request) -> LindaTurn | None:
    """The verified turn behind a request's Bearer token, or None. Cached per request."""
    cached = getattr(request, '_morph_linda_turn', _UNSET)
    if cached is not _UNSET:
        return cached
    turn = _resolve(request)
    request._morph_linda_turn = turn
    return turn


def _resolve(request) -> LindaTurn | None:
    from core.assistant.turn_identity import is_turn_token, resolve_user, verify
    from plugins.installed.agent_mcp.auth import _present_token

    token = _present_token(request)
    if not is_turn_token(token):
        return None
    identity = verify(token)
    if identity is None:
        return None
    try:
        user = resolve_user(identity)
    except Exception:  # noqa: BLE001 — an unresolvable user is an unauthenticated call
        logger.warning('agent_mcp: turn user lookup failed', exc_info=True)
        return None
    if user is None:
        return None
    from core.assistant.modes import resolve_mode

    # The slug in the token was resolved when the turn started; resolve again so
    # a user who lost an entitlement mid-turn loses it on their next tool call.
    mode = resolve_mode(identity.mode, user)
    return LindaTurn(
        user=user,
        conversation_key=identity.conversation_key,
        mode_slug=mode.slug,
        provider=identity.provider,
        model=identity.model,
    )


# Janus keeps what Linda learns in its own memory (core/assistant/janus_learning.py),
# with its own recall. A second memory store would split what she learns, and the
# LindaMemory facts that remain are already injected into her prompt.
ENGINE_OWNED_TOOLS = frozenset({'memory.remember', 'memory.forget', 'memory.recall'})

# ── Linda's catalogue ───────────────────────────────────────────────────────
# Linda runs a store, so she gets every registered store tool inside her scope
# profile except the ones below. Her old hand-picked list hid inventory, SEO and
# catalog writes while showing platform internals, and a live eval timed out on
# half its tasks while she explored db.* and run_python looking for them.

# A shopper's own cart, checkout and wishlist — not the merchant's.
_SHOPPER_PREFIXES = ('cart.', 'checkout.', 'wishlist.')

# Platform internals: only in Developer mode (superusers).
DEVELOPER_TOOLS = frozenset(
    {
        'db.list_models',
        'db.count_rows',
        'db.describe_model',
        'run_python',
        'fs.list_dir',
        'fs.read_file',
        'fs.search_files',
        'system.disk_usage',
        'system.git_log',
        'system.server_info',
        'logs.search',
        'platform.capabilities',
        'plugins.describe',
        'skills.distill',
        'skills.list',
        'skills.record_outcome',
        'delegate.list_agents',
        'delegate.invoke_agent',
        # Blocks for up to 300s inside a turn that has far less.
        'delegate.wait_for_workers',
    }
)

_NOT_LINDAS = ENGINE_OWNED_TOOLS | {
    # Duplicates of the tool Linda uses for the same job; two names for one job
    # cost her a step deciding.
    'catalog.find_products',  # products.search
    'catalog.get_product',  # products.get
    'analytics.revenue_summary',  # analytics.summary
    'cms.list_pages',  # cms.pages
    'orders.list_recent',  # orders.search
    'plugins.enable',  # plugins.toggle
    'plugins.disable',  # plugins.toggle
    # Staff roles are account administration, not store work.
    'rbac.grant_role',
    'rbac.revoke_role',
}

# Tools that act on the world without declaring a write scope.
_CONSENT_ALSO = frozenset(
    {
        'delegate.spawn_workers',  # background runs that spend AI credits
        'meta.sync_audience',  # uploads customer emails to Meta
    }
)
# Write-scoped tools that only compute and store their own report.
_NO_CONSENT = frozenset({'seo.audit_product'})


def _all_tools() -> list:
    """Linda's built-in tools plus every tool an app registered (first name wins)."""
    from core.agents import agent_registry
    from core.assistant.tools import get_default_tools

    by_name: dict[str, Any] = {}
    for tool in [*get_default_tools(), *agent_registry.platform_tools()]:
        by_name.setdefault(tool.name, tool)
    return list(by_name.values())


def catalogue(turn: LindaTurn) -> list:
    """Every tool this turn may see and call: Linda's profile, then the mode."""
    from core.assistant.gates import LINDA_SCOPES

    profile = set(LINDA_SCOPES)
    developer = turn.mode_slug == 'dev'
    tools = [
        t
        for t in _all_tools()
        if set(getattr(t, 'scopes', None) or []) <= profile
        and t.name not in _NOT_LINDAS
        and not t.name.startswith(_SHOPPER_PREFIXES)
        and (developer or t.name not in DEVELOPER_TOOLS)
    ]
    return mode_tools(sorted(tools, key=lambda t: t.name), turn)


def mode_tools(tools: list, turn: LindaTurn) -> list:
    """The part of a catalogue a turn's mode allows."""
    from core.assistant.modes import filter_tools_by_mode

    return filter_tools_by_mode(tools, turn.mode_slug)


def needs_consent(tool) -> bool:
    """Whether a Linda call needs the merchant's own yes first.

    Every write does. The Worker's per-tool ``requires_approval`` flags were set
    for a background agent with its own approval queue, and many writes carry
    none (catalog.update_product, orders.mark_shipped, crm.reply_support); in a
    chat, whatever Linda read could otherwise steer her into making one.
    """
    from core.assistant import gates

    if getattr(tool, 'requires_approval', False):
        return True
    if tool.name in _NO_CONSENT:
        return False
    return tool.name in _CONSENT_ALSO or gates.is_write_tool(tool)


def call_tool(tool, name: str, args: dict, turn: LindaTurn, *, audit_call, audit_denied) -> dict:
    """Run the gate chain, then the tool. Returns an MCP ``tools/call`` result.

    A refusal is returned as an ``isError`` result, not a JSON-RPC error, so the
    model reads the reason verbatim — ``approval_required`` tells it to ask the
    merchant, which is how consent is obtained.
    """
    import time

    from core.assistant import gates

    conv = turn.conversation_key
    human_message, human_message_at = gates.latest_human_turn(conv)
    reason = gates.gate_reason(
        tool=tool,
        tool_name=name,
        args=args,
        scopes=gates.LINDA_SCOPES,
        context={'user': turn.user, 'mode': turn.mode_slug},
        conversation_key=conv,
        human_message=human_message,
        human_message_at=human_message_at,
        needs_consent=needs_consent(tool),
    )
    if reason:
        payload = {'error': reason}
        gates.audit_write_tool(
            tool=tool,
            args=args,
            payload={'refused': reason},
            error_msg=reason,
            conversation_key=conv,
            user=turn.user,
            is_write=needs_consent(tool) or None,
        )
        audit_denied(name, reason.split(':', 1)[0])
        _remember(conv, name, args, payload)
        return _result(payload, is_error=True)

    t0 = time.monotonic()
    error = ''
    try:
        result = tool.invoke(
            args,
            agent=None,
            context={
                'source': 'linda',
                'user': turn.user,
                'mode': turn.mode_slug,
                'conversation_key': conv,
            },
        )
        output = result.output if hasattr(result, 'output') else result
    except Exception as e:  # noqa: BLE001 — a tool failure is reported, never raised
        error = f'{type(e).__name__}: {e}'
        output = {'error': error}
    audit_call(name, args, output=None if error else output, error=error, t0=t0)
    gates.audit_write_tool(
        tool=tool,
        args=args,
        payload=output,
        error_msg=error,
        conversation_key=conv,
        user=turn.user,
        is_write=needs_consent(tool) or None,
    )
    _remember(conv, name, args, output)
    return _result(output, is_error=bool(error))


# Characters of one tool result the model reads. Every step resends the whole
# context, so one oversized result (a full model list, a 1,000-product search)
# slows every later step of the turn.
MAX_RESULT_CHARS = 20_000


def _result(output: Any, *, is_error: bool) -> dict:
    text = json.dumps(output, default=str)
    if len(text) > MAX_RESULT_CHARS:
        text = (
            f'{text[:MAX_RESULT_CHARS]}\n[cut: {len(text) - MAX_RESULT_CHARS} more characters. '
            'Narrow the call (filters, a smaller limit) to see the rest.]'
        )
    return {'content': [{'type': 'text', 'text': text}], 'isError': is_error}


def _remember(conversation_key: str, name: str, args: dict, output: Any) -> None:
    """Record the call in the conversation, as the in-process loop did.

    The chat history is how a merchant sees what Linda did, and the next turn's
    prompt replays it.
    """
    try:
        from core.assistant.persistence import StoredMessage, get_default_store

        payload = output if isinstance(output, (dict, list, str, int, float, bool)) else str(output)
        get_default_store().append(
            conversation_key=conversation_key,
            message=StoredMessage(role='tool', tool_name=name, tool_args=args, tool_output=payload),
        )
    except Exception:  # noqa: BLE001 — history is best-effort; the audit row is the record
        logger.debug('agent_mcp: turn tool message not stored', exc_info=True)

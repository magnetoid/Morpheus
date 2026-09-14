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
    return LindaTurn(user=user, conversation_key=identity.conversation_key, mode_slug=mode.slug)


def mode_tools(tools: list, turn: LindaTurn) -> list:
    """The catalogue a turn's mode allows. Anything else is 'not exposed'."""
    from core.assistant.modes import filter_tools_by_mode

    return filter_tools_by_mode(tools, turn.mode_slug)


def listed_tools(tools: list, turn: LindaTurn) -> list:
    """What ``tools/list`` shows a turn: mode-allowed AND inside Linda's scope profile.

    Hiding out-of-profile tools spares the model calls that can only be refused;
    ``tools/call`` still runs the full gate chain, so this is not the boundary.
    """
    from core.assistant.gates import LINDA_SCOPES

    profile = set(LINDA_SCOPES)
    return [t for t in mode_tools(tools, turn) if set(getattr(t, 'scopes', None) or []) <= profile]


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
    )
    _remember(conv, name, args, output)
    return _result(output, is_error=bool(error))


def _result(output: Any, *, is_error: bool) -> dict:
    return {
        'content': [{'type': 'text', 'text': json.dumps(output, default=str)}],
        'isError': is_error,
    }


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

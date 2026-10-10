"""External agents talk to Janus: the part of the door core owns (ADR 0039).

An agent outside the store (Hermes Agent, OpenClaw, a script) holds an API token
and asks Janus something over MCP or GraphQL. The agent_mcp app owns the door:
it authenticates the token, limits its rate and queues the turn on a worker.
Core owns what a turn is. This module runs one through the same
``Assistant.stream`` every chat uses:

* in a conversation keyed to the token (``gates.external_key``), so only that
  token continues it;
* as the store's staff service user, in the general mode;
* with the token as the turn's principal, so the MCP edge holds every tool call
  to that token's own power. On an external conversation the consent kernel is
  never consulted, so no message there approves anything (``gates.gate_reason``).

Design: docs/plans/janus-external-agents-2026-10.md.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.assistant.external')

#: How an external conversation is titled in the conversation store.
TITLE_PREFIX = 'API: '


def run_turn(*, principal: str, label: str, conversation_key: str, message: str, user) -> dict:
    """Run one Janus turn for an external agent and return its outcome.

    Blocking (a turn can take minutes): call it from a worker. ``user`` is the
    staff service user the door resolved, ``principal`` the token's id; the
    conversation must be that token's.
    """
    from core.assistant import gates
    from core.assistant.runtime import Assistant

    if not principal or gates.principal_of(conversation_key) != principal:
        raise ValueError('This conversation does not belong to the calling token.')
    _ensure_conversation(conversation_key, label)
    result = None
    for event in Assistant().stream(
        message=message,
        conversation_key=conversation_key,
        context={
            'user': user,
            'mcp_public': True,
            'mode': 'general',
            'principal': principal,
            'via': 'api',
            'principal_label': label,
        },
    ):
        if isinstance(event, dict) and event.get('type') in ('final', 'error'):
            result = event.get('result')
    if result is None:
        return {'text': '', 'state': 'failed', 'error': 'Janus returned nothing.', 'tool_calls': 0}
    return {
        'text': str(getattr(result, 'text', '') or ''),
        'state': str(getattr(result, 'state', '') or ''),
        'error': str(getattr(result, 'error', '') or ''),
        'tool_calls': int(getattr(result, 'tool_call_count', 0) or 0),
    }


def _ensure_conversation(key: str, label: str) -> None:
    try:
        from core.assistant.models import AssistantConversation

        AssistantConversation.objects.get_or_create(
            key=key, defaults={'title': (TITLE_PREFIX + (label or 'agent'))[:200]}
        )
    except Exception:  # noqa: BLE001 — the store falls back to files; the turn still runs
        logger.debug('external: conversation row not created', exc_info=True)

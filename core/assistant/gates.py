"""Linda's per-tool-call enforcement chain, callable from any dispatcher.

This is the chain the in-process loop has always run before dispatching a tool
(scope → budget → deadline → approval), lifted out of ``Assistant._gate_reason`` so the MCP
edge can run the SAME code for a Janus turn. Two copies of a safety check drift,
and the looser copy wins where it is read (see CLAUDE.md, ``PROTECTED_PLUGINS``);
one function cannot.

The cooperative deadline (``context['deadline']``, a ``time.monotonic()`` stamp)
only means something inside the process that set it, so the MCP edge passes no
such key and that check is a no-op there. A Janus turn's deadline is its turn
token's expiry, enforced when the token is verified.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger('morpheus.assistant.gates')

#: Linda's scope profile — the store domains a merchant's assistant works in.
#: A contributed tool wanting a scope outside it (a shopper's cart, a new domain)
#: is denied until it is deliberately added here. Every write inside it still
#: needs the merchant's own yes at the MCP edge (``linda_turn.needs_consent``).
LINDA_SCOPES: tuple[str, ...] = (
    'system.read',
    'system.write',
    'diagnostics.read',
    'catalog.read',
    'catalog.write',
    'inventory.read',
    'inventory.write',
    'orders.read',
    'orders.write',
    'orders.cancel',
    'customers.read',
    'customers.write',
    'crm.read',
    'crm.write',
    'analytics.read',
    'seo.read',
    'seo.write',
    'content.write',
    'cms.read',
    'cms.write',
    'promotions.read',
    'promotions.write',
    'gift_cards.read',
    'gift_cards.write',
    'shipping.read',
    'shipping.write',
    'tax.read',
    'tax.write',
    'affiliates.read',
    'affiliates.write',
    'b2b.read',
    'b2b.write',
    'i18n.read',
    'i18n.write',
)


def gate_reason(  # noqa: PLR0911 — flat guard chain, mirrors AgentRuntime
    *,
    tool,
    tool_name: str,
    args: dict,
    scopes,
    context: dict | None,
    conversation_key: str,
    human_message: str,
    spent_tokens: int = 0,
    token_budget: int = 0,
    human_message_at: float | None = None,
    needs_consent: bool | None = None,
) -> str | None:
    """Return a refusal reason, or ``None`` to let the call through.

    ``needs_consent`` overrides the tool's own ``requires_approval`` flag. The MCP
    edge sets it for Linda, who needs the merchant's yes for every write.
    """
    # Scope: an under-scoped caller never reaches an over-scoped tool.
    try:
        from core.agents.policies import ScopeDenied, enforce_policy

        enforce_policy(scopes=list(scopes), required=list(getattr(tool, 'scopes', None) or []))
    except ScopeDenied as e:
        return str(e)
    except Exception:  # noqa: BLE001 — a broken policy import must not open the gate
        logger.warning('assistant: scope check unavailable', exc_info=True)
        return 'scope_check_unavailable'

    # Token budget (0 = unlimited) and the cooperative wall-clock deadline — a
    # timed-out turn stops issuing NEW tool calls instead of running on as a
    # zombie (the reason AgentRuntime polls `context['deadline']`).
    try:
        from core.agents.policies import BudgetExceeded, enforce_budget
        from core.agents.runtime import _deadline_exceeded

        enforce_budget(spent=spent_tokens, cap=token_budget or None)
        if _deadline_exceeded(context or {}):
            return 'deadline_exceeded'
    except BudgetExceeded:
        return 'budget_exceeded'
    except Exception:  # noqa: BLE001 — budget/deadline are advisory, not a gate
        logger.debug('assistant: budget/deadline check skipped', exc_info=True)

    # Approval — kernel-verified HUMAN consent. Staged mode is exempt only for
    # tools that actually stage (`supports_staging`): such a tool records an
    # OpsProposal for review instead of executing, and that proposal IS the
    # sign-off. A tool with no staging path must still pass the gate, or the
    # exemption reopens the S1 hole for the staged path.
    staged = isinstance(context, dict) and context.get('staged')
    staged_exempt = staged and getattr(tool, 'supports_staging', False)
    if needs_consent is None:
        needs_consent = bool(getattr(tool, 'requires_approval', False))
    if needs_consent and not staged_exempt:
        from core.assistant import consent

        if not consent.consume(
            conversation_key=conversation_key,
            tool_name=tool_name,
            args=args,
            human_message=human_message,
            human_message_at=human_message_at,
        ):
            consent.request(conversation_key=conversation_key, tool_name=tool_name, args=args)
            return (
                'approval_required: tell the user exactly what this will do and ask them '
                'to confirm. Do NOT re-call until they have answered — their own reply is '
                'what authorises it, not a `confirmed` argument.'
            )
    return None


def is_write_tool(tool) -> bool:
    return bool(getattr(tool, 'requires_approval', False)) or any(
        'write' in s or s in ('orders.cancel', 'selfdev')
        for s in (getattr(tool, 'scopes', None) or [])
    )


def audit_write_tool(
    *,
    tool,
    args,
    payload,
    error_msg: str,
    conversation_key: str,
    user,
    is_write: bool | None = None,
) -> None:
    """Record a write-tool attempt to core.audit (fail-soft). Reads are skipped.

    A merchant auditing "what did the AI change?" must be able to answer from the
    audit log, not by re-reading conversations — and a REFUSED write is more
    interesting than a successful one, so callers audit refusals too.
    """
    try:
        if not (is_write_tool(tool) if is_write is None else is_write):
            return
        from core.audit.services import record

        record(
            event_type='assistant.tool_write',
            actor=user if getattr(user, 'pk', None) else None,
            target=getattr(tool, 'name', ''),
            severity='warning' if error_msg else 'info',
            metadata={
                'args': json.dumps(args, default=str)[:2000],
                'output_head': json.dumps(payload, default=str)[:500],
                'error': (error_msg or '')[:300],
                'conversation': conversation_key,
            },
        )
    except Exception:  # noqa: BLE001 — auditing must never break the turn
        logger.debug('assistant: write-tool audit skipped', exc_info=True)


def latest_human_turn(conversation_key: str) -> tuple[str, float]:
    """The newest ``role='user'`` message stored for a conversation, and when it was sent.

    Consent is spent only by the human's own words, and this is the one input a
    tool result, product description or fetched page can never write — the chat
    view stores it before the engine starts. The timestamp lets consent refuse a
    message that predates the proposal. An unreadable timestamp is ``0.0``, which
    predates everything, so it fails closed.
    """
    from datetime import datetime

    try:
        from core.assistant.persistence import get_default_store

        for msg in reversed(
            get_default_store().history(conversation_key=conversation_key, limit=30)
        ):
            if msg.role != 'user':
                continue
            try:
                sent_at = datetime.fromisoformat(msg.at).timestamp() if msg.at else 0.0
            except (TypeError, ValueError):
                sent_at = 0.0
            return msg.content or '', sent_at
    except Exception:  # noqa: BLE001 — no message means no consent, never an error
        logger.debug('assistant: latest human message unavailable', exc_info=True)
    return '', 0.0

"""
Agent intent service.

The state machine is enforced here, NOT inside resolvers, so the same flow
works from GraphQL, REST, the Python SDK, and any internal tooling.

    proposed --(authorize)--> authorized --(execute)--> executing
                                                        |       |
                                                        v       v
                                                  completed   failed
              --(reject)----> rejected
              --(expire)----> expired
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from django.db import transaction
from django.utils import timezone
from djmoney.money import Money

from core.hooks import MorpheusEvents, hook_registry
from plugins.installed.ai_assistant.services.receipts import sign_receipt

logger = logging.getLogger('morpheus.agent.intent')


class IntentTransitionError(RuntimeError):
    """Raised when a state transition is invalid for the current intent state."""


class BudgetExceeded(IntentTransitionError):
    """Raised when an intent's cost would exceed the agent's budget cap."""


class CapabilityDenied(IntentTransitionError):
    """Raised when the agent lacks the capability required for this kind of intent."""


_KIND_TO_CAPABILITY = {
    'browse': 'can_browse',
    'compare': 'can_browse',
    'chat': 'can_browse',
    'subscribe': 'can_purchase',
    'cancel': 'can_purchase',
    'checkout': 'can_purchase',
    'return': 'can_purchase',
    'custom': None,
}


@dataclass(slots=True)
class IntentResult:
    intent_id: str
    state: str
    receipt: Optional[dict[str, Any]] = None
    signature: Optional[str] = None


def _enforce_capabilities(agent, kind: str) -> None:
    cap = _KIND_TO_CAPABILITY.get(kind)
    if cap is None:
        return
    if not getattr(agent, cap, False):
        raise CapabilityDenied(f"Agent {agent.agent_id} lacks capability '{cap}' for kind={kind}")


def _enforce_budget(agent, estimated_cost) -> None:
    if estimated_cost is None:
        return
    amount = estimated_cost.amount if hasattr(estimated_cost, 'amount') else Decimal(estimated_cost)
    if not agent.can_afford(amount):
        raise BudgetExceeded(
            f"Agent {agent.agent_id} budget cannot cover {amount} "
            f"(remaining {agent.remaining_budget()})"
        )


def propose(
    *,
    agent,
    kind: str,
    summary: str = '',
    payload: Optional[dict[str, Any]] = None,
    estimated_cost: Optional[Money] = None,
    customer=None,
    channel=None,
    correlation_id: str = '',
    expires_in_seconds: Optional[int] = 600,
) -> 'AgentIntent':  # noqa: F821
    """Create a new intent in the `proposed` state."""
    from plugins.installed.ai_assistant.models import AgentIntent, AgentIntentEvent

    if kind not in {c[0] for c in AgentIntent.KIND_CHOICES}:
        raise IntentTransitionError(f"Unknown intent kind: {kind}")
    _enforce_capabilities(agent, kind)
    _enforce_budget(agent, estimated_cost)

    expires_at = None
    if expires_in_seconds:
        expires_at = timezone.now() + timezone.timedelta(seconds=expires_in_seconds)

    with transaction.atomic():
        intent = AgentIntent.objects.create(
            agent=agent,
            customer=customer,
            channel=channel,
            kind=kind,
            state='proposed',
            summary=summary[:300],
            payload=payload or {},
            estimated_cost=estimated_cost,
            correlation_id=correlation_id[:100],
            expires_at=expires_at,
        )
        AgentIntentEvent.objects.create(
            intent=intent,
            from_state='',
            to_state='proposed',
            actor='agent',
            note='Intent proposed',
        )
    hook_registry.fire(MorpheusEvents.AGENT_INTENT_PROPOSED, intent=intent)
    return intent


def _transition(
    intent,
    *,
    target: str,
    actor: str = 'system',
    note: str = '',
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    from plugins.installed.ai_assistant.models import AgentIntentEvent

    valid: dict[str, set[str]] = {
        'proposed': {'authorized', 'rejected', 'expired'},
        'authorized': {'executing', 'rejected', 'expired'},
        'executing': {'completed', 'failed'},
    }
    allowed = valid.get(intent.state, set())
    if target not in allowed:
        raise IntentTransitionError(
            f"Cannot move intent {intent.id} from {intent.state} -> {target}"
        )
    previous = intent.state
    intent.state = target
    intent.save(update_fields=['state', 'updated_at'])
    AgentIntentEvent.objects.create(
        intent=intent,
        from_state=previous,
        to_state=target,
        actor=actor,
        note=note[:1000] if note else '',
        metadata=metadata or {},
    )


def authorize(intent, *, actor: str = 'customer', note: str = '') -> None:
    """Customer or merchant approves an intent for execution."""
    if intent.expires_at and intent.expires_at < timezone.now():
        with transaction.atomic():
            _transition(intent, target='expired', actor='system', note='Authorization arrived after expiry')
        raise IntentTransitionError('Intent expired before authorization')
    with transaction.atomic():
        _transition(intent, target='authorized', actor=actor, note=note)
    hook_registry.fire(MorpheusEvents.AGENT_INTENT_AUTHORIZED, intent=intent)


def reject(intent, *, actor: str = 'customer', reason: str = '') -> None:
    with transaction.atomic():
        _transition(intent, target='rejected', actor=actor, note=reason)
    hook_registry.fire(MorpheusEvents.AGENT_INTENT_REJECTED, intent=intent)


def begin_execute(intent) -> None:
    with transaction.atomic():
        _transition(intent, target='executing', actor='agent', note='Execution started')


def complete(
    intent,
    *,
    result: Optional[dict[str, Any]] = None,
    actual_cost: Optional[Money] = None,
) -> IntentResult:
    """
    Mark an executing intent as completed, charge the agent budget, sign the
    receipt, and emit `agent.intent.completed` on the event bus.
    """
    from plugins.installed.ai_assistant.models import AgentRegistration

    with transaction.atomic():
        intent.result = {**(intent.result or {}), **(result or {})}
        if actual_cost is not None:
            intent.actual_cost = actual_cost
        intent.save(update_fields=['result', 'actual_cost', 'updated_at'])

        _transition(intent, target='completed', actor='agent', note='Execution completed')

        if actual_cost is not None:
            AgentRegistration.objects.filter(pk=intent.agent_id).update(
                total_spend_amount=models_F_add('total_spend_amount', actual_cost.amount),
                total_orders=models_F_add('total_orders', 1),
                last_active_at=timezone.now(),
            )

        intent.refresh_from_db()
        payload, signature = sign_receipt(intent, intent.agent.signing_secret)
        intent.receipt_signature = signature
        intent.receipt_signed_at = timezone.now()
        intent.save(update_fields=['receipt_signature', 'receipt_signed_at', 'updated_at'])

    hook_registry.fire(MorpheusEvents.AGENT_INTENT_COMPLETED, intent=intent, receipt=payload, signature=signature)
    return IntentResult(intent_id=str(intent.id), state=intent.state, receipt=payload, signature=signature)


def fail(intent, *, error: str, metadata: Optional[dict[str, Any]] = None) -> None:
    with transaction.atomic():
        intent.result = {**(intent.result or {}), 'error': error[:500]}
        intent.save(update_fields=['result', 'updated_at'])
        _transition(intent, target='failed', actor='agent', note=error, metadata=metadata)
    hook_registry.fire(MorpheusEvents.AGENT_INTENT_FAILED, intent=intent, error=error)


def models_F_add(field: str, amount):
    """Wrap an F() expression that adds amount to a numeric field, COALESCEing nulls."""
    from django.db.models import F, Value
    from django.db.models.functions import Coalesce
    return Coalesce(F(field), Value(0)) + amount

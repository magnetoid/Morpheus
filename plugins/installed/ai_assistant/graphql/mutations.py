"""GraphQL mutations exposed by the AI Assistant plugin.

These cover the agent intent lifecycle and are the canonical surface for any
external AI agent (LLM, browser-use, MCP, A2A) to act against the platform.
"""

from __future__ import annotations

from decimal import Decimal

import strawberry
from djmoney.money import Money

from api.graphql_permissions import (
    PermissionDenied,
    current_customer,
    require_authenticated,
)


@strawberry.type
class AgentIntentReceipt:
    intent_id: strawberry.ID
    state: str
    signature: str
    issued_at: str


@strawberry.type
class AgentIntentType:
    id: strawberry.ID
    kind: str
    state: str
    summary: str
    receipt_signature: str


@strawberry.input
class ProposeIntentInput:
    kind: str
    summary: str = ''
    payload_json: str | None = None
    estimated_amount: float | None = None
    estimated_currency: str = 'USD'
    correlation_id: str = ''
    expires_in_seconds: int = 600


def _resolve_agent(info) -> AgentRegistration:  # noqa: F821
    """Pull the AgentRegistration for the current request, or raise."""
    request = (
        info.context.get('request')
        if isinstance(info.context, dict)
        else getattr(info.context, 'request', None)
    )
    ai_ctx = getattr(request, 'ai_context', None)
    if not ai_ctx or not ai_ctx.agent_capabilities.get('agent_pk'):
        raise PermissionDenied('Agent token required')
    from plugins.installed.ai_assistant.models import AgentRegistration

    try:
        return AgentRegistration.objects.get(pk=ai_ctx.agent_capabilities['agent_pk'])
    except AgentRegistration.DoesNotExist as e:
        raise PermissionDenied('Agent not found') from e


def _load_intent(info, intent_id: str) -> AgentIntent:  # noqa: F821
    from plugins.installed.ai_assistant.models import AgentIntent

    intent = AgentIntent.objects.select_related('agent', 'customer').get(pk=intent_id)
    request = (
        info.context.get('request')
        if isinstance(info.context, dict)
        else getattr(info.context, 'request', None)
    )
    ai_ctx = getattr(request, 'ai_context', None)
    if ai_ctx and ai_ctx.agent_capabilities.get('agent_pk'):
        if str(intent.agent_id) != ai_ctx.agent_capabilities['agent_pk']:
            raise PermissionDenied('Intent does not belong to this agent')
        return intent
    customer = current_customer(info)
    if customer and intent.customer_id == customer.pk:
        return intent
    raise PermissionDenied('Not allowed to access this intent')


@strawberry.type
class AIAssistantMutationExtension:
    @strawberry.mutation(description='Propose a new agent intent (requires agent token)')
    def propose_agent_intent(
        self,
        info: strawberry.Info,
        input: ProposeIntentInput,
    ) -> AgentIntentType:
        import json

        from plugins.installed.ai_assistant.services import intent as intent_service

        agent = _resolve_agent(info)
        payload = {}
        if input.payload_json:
            try:
                payload = json.loads(input.payload_json)
            except json.JSONDecodeError as e:
                raise PermissionDenied(f'Invalid payload_json: {e}') from e

        estimated = None
        if input.estimated_amount is not None:
            estimated = Money(Decimal(str(input.estimated_amount)), input.estimated_currency)

        intent = intent_service.propose(
            agent=agent,
            kind=input.kind,
            summary=input.summary,
            payload=payload,
            estimated_cost=estimated,
            customer=current_customer(info),
            correlation_id=input.correlation_id,
            expires_in_seconds=input.expires_in_seconds,
        )
        return AgentIntentType(
            id=str(intent.id),
            kind=intent.kind,
            state=intent.state,
            summary=intent.summary,
            receipt_signature=intent.receipt_signature,
        )

    @strawberry.mutation(description='Authorize a proposed agent intent (customer/merchant action)')
    def authorize_agent_intent(
        self,
        info: strawberry.Info,
        intent_id: strawberry.ID,
        note: str = '',
    ) -> AgentIntentType:
        require_authenticated(info)
        from plugins.installed.ai_assistant.services import intent as intent_service

        intent = _load_intent(info, str(intent_id))
        intent_service.authorize(intent, actor='customer', note=note)
        intent.refresh_from_db()
        return AgentIntentType(
            id=str(intent.id),
            kind=intent.kind,
            state=intent.state,
            summary=intent.summary,
            receipt_signature=intent.receipt_signature,
        )

    @strawberry.mutation(description='Reject a proposed agent intent')
    def reject_agent_intent(
        self,
        info: strawberry.Info,
        intent_id: strawberry.ID,
        reason: str = '',
    ) -> AgentIntentType:
        require_authenticated(info)
        from plugins.installed.ai_assistant.services import intent as intent_service

        intent = _load_intent(info, str(intent_id))
        intent_service.reject(intent, actor='customer', reason=reason)
        intent.refresh_from_db()
        return AgentIntentType(
            id=str(intent.id),
            kind=intent.kind,
            state=intent.state,
            summary=intent.summary,
            receipt_signature=intent.receipt_signature,
        )

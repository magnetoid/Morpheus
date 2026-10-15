"""
AI Assistant — AIContext Middleware
Attaches an AIContext (agent capabilities, customer id) to every request.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.db import DatabaseError

logger = logging.getLogger('morpheus.ai.context')


@dataclass
class AIContext:
    """Enriched context attached to every request for AI personalisation."""

    customer_id: str | None = None
    agent_id: str | None = None
    agent_capabilities: dict = field(default_factory=dict)
    session_intent: str | None = None
    personalization_tier: str = 'none'
    experiment_assignments: dict = field(default_factory=dict)

    @property
    def is_agent(self) -> bool:
        return bool(self.agent_id)

    @property
    def is_personalized(self) -> bool:
        return self.personalization_tier in ('basic', 'full')


class AIContextMiddleware:
    """Attach AIContext to request.ai_context for all views and resolvers."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.ai_context = self._build_context(request)
        return self.get_response(request)

    def _resolve_agent_token(self, request) -> str | None:
        token = request.headers.get('X-Agent-Token')
        if token:
            return token.strip()
        auth = request.headers.get('Authorization', '')
        if auth.startswith('AgentToken '):
            return auth[len('AgentToken ') :].strip()
        return None

    def _attach_agent(self, ctx: AIContext, agent_token: str) -> bool:
        from plugins.installed.ai_assistant.models import AgentRegistration

        try:
            agent = AgentRegistration.objects.get(token=agent_token, is_active=True)
        except AgentRegistration.DoesNotExist:
            return False
        except DatabaseError as e:
            logger.warning('AIContext: DB error resolving agent token: %s', e)
            return False

        ctx.agent_id = agent.agent_id
        ctx.agent_capabilities = {
            'agent_pk': str(agent.pk),
            'can_browse': agent.can_browse,
            'can_purchase': agent.can_purchase,
            'can_manage_inventory': agent.can_manage_inventory,
            'budget_limit': str(agent.budget_limit_amount) if agent.budget_limit_amount else None,
            'allowed_categories': agent.allowed_categories,
        }
        ctx.personalization_tier = 'full'
        return True

    def _build_context(self, request) -> AIContext:
        ctx = AIContext()

        agent_token = self._resolve_agent_token(request)
        if agent_token and self._attach_agent(ctx, agent_token):
            return ctx

        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            ctx.customer_id = str(user.id)
            ctx.personalization_tier = 'full'

        return ctx

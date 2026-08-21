"""GraphQL queries exposed by the AI Assistant plugin."""

from __future__ import annotations

import strawberry

from api.graphql_permissions import (
    PermissionDenied,
    current_customer,
)
from plugins.installed.catalog.graphql.types import ProductType


@strawberry.type
class SemanticSearchResult:
    products: list[ProductType]
    explanation: str
    used_embedding: bool


@strawberry.type
class AgentIntentSummaryType:
    id: strawberry.ID
    kind: str
    state: str
    summary: str
    correlation_id: str
    receipt_signature: str
    created_at: str


_SEMANTIC_SEARCH_PER_MINUTE = 30


def _embedding_budget_exhausted(info) -> bool:
    """Per-client budget for the embedding path (fixed 60s window).

    Keyed on the token bucket when present, else the client IP. Fail-OPEN on a
    cache outage: search availability beats spend control, and the provider
    call is itself bounded by the model's own limits.
    """
    request = None
    ctx = getattr(info, 'context', None)
    if isinstance(ctx, dict):
        request = ctx.get('request')
    elif ctx is not None:
        request = getattr(ctx, 'request', None)
    if request is None:
        return False
    client = request.META.get('HTTP_CF_CONNECTING_IP') or request.META.get('REMOTE_ADDR') or 'anon'
    try:
        import time

        from django.core.cache import cache

        key = f'ai:semsearch:{client}:{int(time.time() // 60)}'
        try:
            count = cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=120)
            count = 1
    except Exception:  # noqa: BLE001 — availability over strictness
        return False
    return count > _SEMANTIC_SEARCH_PER_MINUTE


@strawberry.type
class AIAssistantQueryExtension:
    @strawberry.field(description='Embedding-backed semantic product search with safe fallback.')
    def semantic_search(
        self,
        info: strawberry.Info,
        query: str,
        first: int = 8,
    ) -> SemanticSearchResult:
        from plugins.installed.ai_assistant.services.search import semantic_search as run_search

        first = max(1, min(int(first), 24))
        query = (query or '').strip()
        if not query:
            return SemanticSearchResult(
                products=[], explanation='Empty query.', used_embedding=False
            )

        # Cost guard. This field is PUBLIC (storefront search), and each miss
        # computes an embedding — i.e. an unauthenticated caller could drive
        # provider spend at request rate. Requiring auth would break storefront
        # search, so instead budget the EXPENSIVE path per client: over budget,
        # degrade to keyword search (no embed call, no spend) rather than error.
        if _embedding_budget_exhausted(info):
            from plugins.installed.ai_assistant.services.search import _keyword_fallback

            return SemanticSearchResult(
                products=_keyword_fallback(query, first),
                explanation=f"Showing keyword matches for '{query}'.",
                used_embedding=False,
            )

        products, used_embedding = run_search(query, limit=first)
        if used_embedding:
            explanation = (
                f"Found {len(products)} products that semantically match '{query}' "
                f'using vector similarity over product embeddings.'
            )
        else:
            explanation = f"No embeddings available — falling back to keyword search for '{query}'."
        return SemanticSearchResult(
            products=products,
            explanation=explanation,
            used_embedding=used_embedding,
        )

    @strawberry.field(description="List the current caller's agent intents (customer or agent).")
    def my_agent_intents(
        self,
        info: strawberry.Info,
        first: int = 25,
        state: str | None = None,
    ) -> list[AgentIntentSummaryType]:
        from plugins.installed.ai_assistant.models import AgentIntent

        request = (
            info.context.get('request')
            if isinstance(info.context, dict)
            else getattr(info.context, 'request', None)
        )
        ai_ctx = getattr(request, 'ai_context', None)
        agent_pk = ai_ctx.agent_capabilities.get('agent_pk') if ai_ctx else None

        first = max(1, min(int(first), 100))
        qs = AgentIntent.objects.select_related('agent').order_by('-created_at')

        if agent_pk:
            qs = qs.filter(agent_id=agent_pk)
        else:
            customer = current_customer(info)
            if customer is None:
                raise PermissionDenied('Authentication required')
            qs = qs.filter(customer=customer)

        if state:
            qs = qs.filter(state=state)

        return [
            AgentIntentSummaryType(
                id=str(i.id),
                kind=i.kind,
                state=i.state,
                summary=i.summary,
                correlation_id=i.correlation_id,
                receipt_signature=i.receipt_signature,
                created_at=i.created_at.isoformat(),
            )
            for i in qs[:first]
        ]

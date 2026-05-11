"""
Hardened GraphQL view.

- Pre-validates queries for depth/alias limits to mitigate DoS-style nested queries.
- Maps PermissionDenied raised from resolvers to a clean GraphQL error code.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from graphql import GraphQLError
from graphql.language.ast import FieldNode
from strawberry.django.views import GraphQLView

logger = logging.getLogger('morpheus.api.graphql')


class MorpheusGraphQLView(GraphQLView):
    """GraphQL view with extra hardening."""

    agent_only = False

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if self.agent_only and not getattr(request, 'agent_capabilities', None):
            return JsonResponse(
                {'error': 'Unauthorized: missing or invalid Agent Token'},
                status=401,
            )

        # Pre-validate body before strawberry parses/executes the query.
        if request.method == 'POST' and request.content_type == 'application/json':
            try:
                body = json.loads(request.body or b'{}')
            except json.JSONDecodeError:
                body = None
            if isinstance(body, dict):
                try:
                    self._validate_complexity(body, allow_introspection=self.agent_only)
                except GraphQLError as e:
                    return JsonResponse({'errors': [{'message': str(e)}]}, status=400)

        return super().dispatch(request, *args, **kwargs)

    @staticmethod
    def _validate_complexity(data: dict[str, Any], *, allow_introspection: bool = False) -> None:
        """Reject queries that exceed depth/alias limits, or — in production —
        attempt schema introspection. Runs before strawberry parses/executes.

        ``allow_introspection=True`` (set by the agent-auth route) lets
        Bearer-authenticated clients hit ``__schema`` / ``__type`` — they
        need it to generate typed clients from the live schema.
        """
        from graphql import parse

        query = data.get('query')
        if not query:
            return

        max_depth = getattr(settings, 'GRAPHQL_MAX_QUERY_DEPTH', 10)
        max_aliases = getattr(settings, 'GRAPHQL_MAX_ALIASES', 15)
        block_introspection = (
            not allow_introspection
            and not settings.DEBUG
            and getattr(settings, 'GRAPHQL_DISABLE_INTROSPECTION_IN_PROD', True)
        )

        try:
            document = parse(query)
        except Exception as e:  # noqa: BLE001 — let strawberry produce the canonical error
            logger.debug("Query parse failed in pre-validation: %s", e)
            return

        alias_count = 0

        def visit(node: Any, depth: int) -> None:
            nonlocal alias_count
            if depth > max_depth:
                raise GraphQLError(f"Query exceeds maximum depth of {max_depth}")
            selection_set = getattr(node, 'selection_set', None)
            if not selection_set:
                return
            for selection in selection_set.selections:
                if isinstance(selection, FieldNode):
                    name = selection.name.value
                    if block_introspection and name in ('__schema', '__type'):
                        raise GraphQLError(
                            'GraphQL introspection is disabled in production.',
                        )
                    if selection.alias is not None:
                        alias_count += 1
                        if alias_count > max_aliases:
                            raise GraphQLError(
                                f"Query exceeds maximum aliases of {max_aliases}",
                            )
                visit(selection, depth + 1)

        for definition in document.definitions:
            visit(definition, 0)


def morpheus_graphql_view(agent_only: bool = False):
    """Factory used from urls.py to wire the singleton schema into a view.

    The agent-auth route is wrapped in ``csrf_exempt`` — it uses Bearer
    tokens, never session cookies, so the CSRF middleware would just
    block legitimate external clients (Lumina, Claude Desktop, etc.).
    """
    from api.schema import get_schema
    view = MorpheusGraphQLView.as_view(schema=get_schema(), agent_only=agent_only)
    if agent_only:
        view = csrf_exempt(view)
    return view

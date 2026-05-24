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
        # Bearer-token auth: external agents present an MCP token from
        # /dashboard/apps/agent_mcp/tokens/ in the Authorization header
        # so they don't have to juggle Django session cookies. When a
        # valid token is presented, `request.user` is replaced with a
        # synthetic staff service user so resolvers that check
        # `is_staff` (the catalog mutations) accept the call. No-op
        # otherwise; session cookies still work.
        try:
            from plugins.installed.agent_mcp.auth import apply_bearer_user
            apply_bearer_user(request)
        except Exception as e:  # noqa: BLE001 — never block the request on auth resolver
            logger.warning('agent_mcp: bearer auth resolver failed: %s', e, exc_info=True)

        if self.agent_only and not getattr(request, 'agent_capabilities', None):
            return JsonResponse(
                {'error': 'Unauthorized: missing or invalid Agent Token'},
                status=401,
            )

        # Pre-validate body before strawberry parses/executes the query.
        # Also pull the operation type so we can set cache headers below.
        body_dict: dict[str, Any] | None = None
        if request.method == 'POST' and request.content_type == 'application/json':
            try:
                body_dict = json.loads(request.body or b'{}')
            except json.JSONDecodeError:
                body_dict = None
            if isinstance(body_dict, dict):
                try:
                    self._validate_complexity(body_dict, allow_introspection=self.agent_only)
                except GraphQLError as e:
                    return JsonResponse({'errors': [{'message': str(e)}]}, status=400)

        response = super().dispatch(request, *args, **kwargs)
        self._attach_cache_headers(request, response, body_dict)
        return response

    def _attach_cache_headers(
        self, request: HttpRequest, response: HttpResponse,
        body: dict[str, Any] | None,
    ) -> None:
        """Emit Cache-Control + Vary on the GraphQL response so a CDN
        in front of the origin (Cloudflare) can cache identical read
        queries at the edge.

        Cacheable only when:
          - response status is 2xx
          - operation is a `query` (not mutation/subscription)
          - request carries no Authorization header and no agent token
          - storefront plugin config `graphql_edge_cache_ttl` > 0

        Otherwise: `Cache-Control: no-store, private` so neither the
        browser nor any intermediary stashes a session-coloured payload.

        IMPORTANT: Cloudflare does not cache POST responses out of the
        box. To actually benefit from this header for POST /graphql/,
        the merchant needs a Cloudflare Cache Rule that opts POST in.
        See docs/UI_STYLE_GUIDE.md §11 (or the Caching settings page).
        """
        try:
            if response.status_code >= 300:
                response['Cache-Control'] = 'no-store, private'
                return

            is_authenticated = bool(
                request.META.get('HTTP_AUTHORIZATION')
                or getattr(request, 'user', None) and request.user.is_authenticated
                or getattr(request, 'agent_capabilities', None)
            )

            op_type = self._operation_type(body)
            ttl = self._graphql_edge_ttl()

            if op_type == 'query' and not is_authenticated and ttl > 0:
                response['Cache-Control'] = (
                    f'public, s-maxage={ttl}, max-age=0, must-revalidate'
                )
                # Vary on Authorization so CF correctly separates
                # anonymous from authenticated cached entries even if
                # the CF rule keys on full URL only.
                response['Vary'] = 'Authorization, Cookie, Accept-Encoding'
                # Cache-Tag lets us purge by tag from the CF app.
                response['Cache-Tag'] = 'graphql,graphql:query'
            else:
                response['Cache-Control'] = 'no-store, private'
        except Exception as e:  # noqa: BLE001 — never block the response over a header bug
            logger.debug('graphql cache-header attach failed: %s', e)

    @staticmethod
    def _operation_type(body: dict[str, Any] | None) -> str:
        """Return 'query' / 'mutation' / 'subscription' or '' if unknown.

        Cheap parse — looks at the first non-whitespace keyword in the
        query string. A full graphql.parse() would be exact but the
        keyword sniff is fine for the cache decision and 50× faster.
        """
        if not isinstance(body, dict):
            return ''
        q = (body.get('query') or '').lstrip()
        if not q:
            return ''
        # Anonymous query shorthand starts with `{` → it's a query.
        if q.startswith('{'):
            return 'query'
        first_word = q.split(None, 1)[0].lower()
        return first_word if first_word in ('query', 'mutation', 'subscription') else ''

    @staticmethod
    def _graphql_edge_ttl() -> int:
        """Read the merchant-configured edge TTL for GraphQL queries.

        Stored on storefront PluginConfig — falls back to 0 (no edge
        caching) when unconfigured so the default behaviour is safe.
        """
        try:
            from plugins.registry import plugin_registry
            p = plugin_registry.get('storefront')
            if p is None:
                return 0
            return max(0, int(p.get_config().get('graphql_edge_cache_ttl') or 0))
        except Exception:  # noqa: BLE001
            return 0

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

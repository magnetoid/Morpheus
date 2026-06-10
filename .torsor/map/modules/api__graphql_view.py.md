---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:48'
updated: '2026-06-10T20:08:48'
---

# api/graphql_view.py

Symbols in `api/graphql_view.py`.

- L23 `MorpheusGraphQLView` (class) — GraphQL view with extra hardening.
- L28 `dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any)` (method)
- L66 `_attach_cache_headers(self, request: HttpRequest, response: HttpResponse, body: dict[str, Any] | None)` (method) — Emit Cache-Control + Vary on the GraphQL response so a CDN
- L127 `_operation_type(body: dict[str, Any] | None)` (method) — Return 'query' / 'mutation' / 'subscription' or '' if unknown.
- L146 `_extract_entity_tags(body: dict[str, Any] | None)` (method) — Derive per-entity Cache-Tags from the GraphQL query.
- L231 `_graphql_edge_ttl()` (method) — Read the merchant-configured edge TTL for GraphQL queries.
- L247 `_validate_complexity(data: dict[str, Any], *, allow_introspection: bool=False)` (method) — Reject queries that exceed depth/alias limits, or — in production —
- L303 `morpheus_graphql_view(agent_only: bool=False)` (function) — Factory used from urls.py to wire the singleton schema into a view.

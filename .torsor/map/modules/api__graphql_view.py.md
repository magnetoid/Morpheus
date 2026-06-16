---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:56'
updated: '2026-06-13T00:49:56'
---

# api/graphql_view.py

Symbols in `api/graphql_view.py`.

- L24 `MorpheusGraphQLView` (class) — GraphQL view with extra hardening.
- L29 `dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any)` (method)
- L68 `_attach_cache_headers(self, request: HttpRequest, response: HttpResponse, body: dict[str, Any] | None)` (method) — Emit Cache-Control + Vary on the GraphQL response so a CDN
- L130 `_operation_type(body: dict[str, Any] | None)` (method) — Return 'query' / 'mutation' / 'subscription' or '' if unknown.
- L149 `_extract_entity_tags(body: dict[str, Any] | None)` (method) — Derive per-entity Cache-Tags from the GraphQL query.
- L242 `_graphql_edge_ttl()` (method) — Read the merchant-configured edge TTL for GraphQL queries.
- L259 `_validate_complexity(data: dict[str, Any], *, allow_introspection: bool=False)` (method) — Reject queries that exceed depth/alias limits, or — in production —
- L315 `morpheus_graphql_view(agent_only: bool=False)` (function) — Factory used from urls.py to wire the singleton schema into a view.

---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:56'
updated: '2026-06-13T00:49:56'
---

# api/graphql_permissions.py

Symbols in `api/graphql_permissions.py`.

- L24 `PermissionDenied` (class) — Raised when a resolver detects an unauthorized caller.
- L28 `get_request(info: strawberry.Info)` (function)
- L36 `is_authenticated(info: strawberry.Info)` (function) — True for any authenticated principal (session user, token, API key, agent).
- L51 `has_scope(info: strawberry.Info, scope: str)` (function) — True when the caller has the given scope, or admin/staff equivalence.
- L72 `require_scope(info: strawberry.Info, scope: str)` (function) — Raise PermissionDenied unless the caller has the scope.
- L78 `require_authenticated(info: strawberry.Info)` (function)
- L83 `current_customer(info: strawberry.Info)` (function) — Return the logged-in Customer or None (no exception).
- L94 `current_channel_id(info: strawberry.Info)` (function) — Channel scoping for multi-tenant resolvers — returns None when unscoped.

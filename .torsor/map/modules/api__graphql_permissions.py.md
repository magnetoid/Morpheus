---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:51'
updated: '2026-06-02T18:07:51'
---

# api/graphql_permissions.py

Symbols in `api/graphql_permissions.py`.

- L23 `PermissionDenied` (class) — Raised when a resolver detects an unauthorized caller.
- L27 `get_request(info: strawberry.Info)` (function)
- L35 `is_authenticated(info: strawberry.Info)` (function) — True for any authenticated principal (session user, token, API key, agent).
- L50 `has_scope(info: strawberry.Info, scope: str)` (function) — True when the caller has the given scope, or admin/staff equivalence.
- L71 `require_scope(info: strawberry.Info, scope: str)` (function) — Raise PermissionDenied unless the caller has the scope.
- L77 `require_authenticated(info: strawberry.Info)` (function)
- L82 `current_customer(info: strawberry.Info)` (function) — Return the logged-in Customer or None (no exception).
- L93 `current_channel_id(info: strawberry.Info)` (function) — Channel scoping for multi-tenant resolvers — returns None when unscoped.

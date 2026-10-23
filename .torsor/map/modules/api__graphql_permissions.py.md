---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# api/graphql_permissions.py

Symbols in `api/graphql_permissions.py`.

- L24 `PermissionDenied` (class) — Raised when a resolver detects an unauthorized caller.
- L28 `get_request(info: strawberry.Info)` (function)
- L36 `is_authenticated(info: strawberry.Info)` (function) — True for any authenticated principal (session user, token, API key, agent).
- L51 `is_staff(info: strawberry.Info)` (function) — True when the request principal is a staff user.
- L93 `has_scope(info: strawberry.Info, scope: str)` (function) — True when the caller has the given scope, or admin/staff equivalence.
- L146 `mutation_scope_error(info: strawberry.Info, required: list[str])` (function) — '' when the caller may run a staff mutation needing one of `required`; else why not.
- L170 `require_scope(info: strawberry.Info, scope: str)` (function) — Raise PermissionDenied unless the caller has the scope.
- L176 `require_authenticated(info: strawberry.Info)` (function)
- L181 `current_customer(info: strawberry.Info)` (function) — Return the logged-in Customer or None (no exception).
- L192 `current_channel_id(info: strawberry.Info)` (function) — Channel scoping for multi-tenant resolvers — returns None when unscoped.

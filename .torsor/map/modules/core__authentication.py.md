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

# core/authentication.py

Symbols in `core/authentication.py`.

- L20 `MorpheusAPIKeyAuthentication` (class) — Validates `Authorization: Bearer <key>` against the APIKey table.
- L28 `authenticate(self, request: Request)` (method)
- L48 `authenticate_credentials(self, key: str, request: Request | None=None)` (method)
- L64 `HasScopePermission` (class) — DRF permission that checks the authenticated APIKey carries a required scope.
- L76 `for_scope(cls, scope: str)` (method)
- L83 `has_permission(self, request: Request, view: APIView)` (method)

---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/authentication.py

Symbols in `core/authentication.py`.

- L20 `MorpheusAPIKeyAuthentication` (class) — Validates `Authorization: Bearer <key>` against the APIKey table.
- L28 `authenticate(self, request: Request)` (method)
- L48 `authenticate_credentials(self, key: str, request: Request | None=None)` (method)
- L60 `HasScopePermission` (class) — DRF permission that checks the authenticated APIKey carries a required scope.
- L72 `for_scope(cls, scope: str)` (method)
- L79 `has_permission(self, request: Request, view: APIView)` (method)

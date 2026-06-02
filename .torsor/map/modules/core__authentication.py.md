---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:51'
updated: '2026-06-02T18:07:51'
---

# core/authentication.py

Symbols in `core/authentication.py`.

- L19 `MorpheusAPIKeyAuthentication` (class) — Validates `Authorization: Bearer <key>` against the APIKey table.
- L26 `authenticate(self, request: 'Request')` (method)
- L46 `authenticate_credentials(self, key: str, request: Optional['Request']=None)` (method)
- L58 `HasScopePermission` (class) — DRF permission that checks the authenticated APIKey carries a required scope.
- L69 `for_scope(cls, scope: str)` (method)
- L76 `has_permission(self, request: 'Request', view: 'APIView')` (method)

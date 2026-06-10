---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:48'
updated: '2026-06-10T20:08:48'
---

# core/authentication.py

Symbols in `core/authentication.py`.

- L19 `MorpheusAPIKeyAuthentication` (class) — Validates `Authorization: Bearer <key>` against the APIKey table.
- L26 `authenticate(self, request: 'Request')` (method)
- L46 `authenticate_credentials(self, key: str, request: Optional['Request']=None)` (method)
- L58 `HasScopePermission` (class) — DRF permission that checks the authenticated APIKey carries a required scope.
- L69 `for_scope(cls, scope: str)` (method)
- L76 `has_permission(self, request: 'Request', view: 'APIView')` (method)

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

# api/tests_graphql_permissions.py

Symbols in `api/tests_graphql_permissions.py`.

- L21 `_Info` (class) — Minimal strawberry.Info stand-in — only context['request'] is read.
- L24 `__init__(self, request)` (method)
- L28 `_req(*, staff=False, graphql_scopes=None)` (function)
- L43 `HasScopeTokenBoundaryTests` (class)
- L44 `test_scoped_token_is_confined_to_its_scopes(self)` (method)
- L52 `test_wildcard_token_passes_anything(self)` (method)
- L57 `test_empty_token_scope_set_denies(self)` (method)
- L61 `test_session_staff_without_a_token_keeps_the_is_staff_fallback(self)` (method)
- L67 `test_anonymous_without_a_token_is_denied(self)` (method)
- L73 `VendorOrderIsolationTests` (class) — myVendorOrders must return only the caller's own vendor rows (IDOR).
- L76 `_vendor_with_owner(self, name, slug)` (method)
- L85 `test_vendor_sees_only_own_orders(self)` (method)
- L119 `CapabilitySeamTests` (class) — Session staff are authorized through the RBAC capability seam.
- L129 `test_mapped_scope_routes_through_check(self)` (method)
- L139 `test_enforce_mode_denial_propagates(self)` (method)
- L146 `test_unmapped_scope_keeps_is_staff_fallback(self)` (method)
- L152 `test_token_callers_are_unaffected_by_the_seam(self)` (method)

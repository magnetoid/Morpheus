---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/orders/tests/test_graphql_cart_ownership.py

Symbols in `plugins/installed/orders/tests/test_graphql_cart_ownership.py`.

- L31 `_Info` (class)
- L32 `__init__(self, request)` (method)
- L36 `_session()` (function)
- L42 `_req(session, *, user=None, graphql_scopes=None)` (function)
- L51 `CartMutationOwnershipTests` (class)
- L52 `setUp(self)` (method)
- L67 `test_foreign_session_cannot_update_item(self)` (method)
- L77 `test_foreign_session_cannot_set_shipping_rate(self)` (method)
- L86 `test_foreign_session_cannot_apply_coupon(self)` (method)
- L91 `test_foreign_session_cannot_complete_order(self)` (method)
- L111 `test_owner_can_update_item(self)` (method)
- L121 `test_read_carts_token_can_mutate(self)` (method)
- L129 `test_add_to_cart_ignores_supplied_session_key(self)` (method)
- L149 `test_cart_type_session_key_is_blanked(self)` (method)

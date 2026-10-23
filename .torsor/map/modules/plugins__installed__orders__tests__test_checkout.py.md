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

# plugins/installed/orders/tests/test_checkout.py

Symbols in `plugins/installed/orders/tests/test_checkout.py`.

- L27 `CheckoutFlowTests` (class)
- L28 `setUp(self)` (method)
- L50 `test_add_to_cart_creates_cart_and_item(self)` (method)
- L59 `test_mixing_currencies_in_one_cart_is_rejected(self)` (method)
- L72 `test_create_from_cart_emits_order_and_clears_cart(self)` (method)
- L104 `test_create_from_cart_stamps_visitor_id_into_metadata(self)` (method)
- L124 `test_order_placement_reserves_stock(self)` (method)
- L139 `test_reservation_is_idempotent(self)` (method)
- L157 `test_commit_decrements_stock_after_payment(self)` (method)
- L173 `test_release_on_cancel(self)` (method)
- L185 `test_oversell_is_blocked_at_checkout(self)` (method)
- L213 `test_order_confirmation_email_is_sent(self)` (method)

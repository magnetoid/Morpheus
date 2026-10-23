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

# plugins/installed/loyalty_points/tests/test_smoke.py

Symbols in `plugins/installed/loyalty_points/tests/test_smoke.py`.

- L13 `LoyaltySmoke` (class)
- L14 `setUp(self)` (method)
- L21 `test_award_and_balance(self)` (method)
- L30 `test_order_paid_hook_registered(self)` (method)
- L39 `LoyaltyGuestGuard` (class) — The ORDER_PAID handler must award points only to authenticated customers,
- L44 `setUp(self)` (method)
- L51 `_order(self, customer, *, total=25, number='G-1')` (method)
- L56 `test_authenticated_customer_earns(self)` (method)
- L62 `test_guest_without_is_authenticated_earns_nothing(self)` (method)

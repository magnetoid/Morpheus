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

# plugins/installed/orders/tests/test_expire_pending.py

Symbols in `plugins/installed/orders/tests/test_expire_pending.py`.

- L36 `ExpirePendingOrdersTests` (class)
- L37 `setUp(self)` (method)
- L49 `_place(self, session_key='s-exp')` (method)
- L56 `_age(self, order, minutes)` (method)
- L61 `_reserved(self)` (method)
- L65 `test_stale_unpaid_order_is_cancelled_and_stock_released(self)` (method)
- L77 `test_recent_order_is_left_alone(self)` (method)
- L82 `test_paid_order_is_never_cancelled(self)` (method)
- L90 `test_zero_minutes_disables_the_sweep(self)` (method)
- L106 `test_sweep_is_idempotent(self)` (method)
- L113 `test_offline_gateway_orders_are_not_expired(self)` (method) — Cash on delivery and bank transfer are paid later by design. The

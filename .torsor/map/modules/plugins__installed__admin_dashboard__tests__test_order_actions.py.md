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

# plugins/installed/admin_dashboard/tests/test_order_actions.py

Symbols in `plugins/installed/admin_dashboard/tests/test_order_actions.py`.

- L23 `_order(payment_status='unpaid')` (function)
- L34 `MarkOrderPaidTests` (class)
- L35 `test_mark_paid_fires_order_paid_once_and_is_idempotent(self)` (method)
- L58 `MarkPaidConfirmsTests` (class) — A cash or bank-transfer order marked paid is confirmed, like an online
- L62 `test_mark_paid_confirms_a_pending_order(self)` (method)
- L68 `test_mark_paid_leaves_a_shipped_order_shipped(self)` (method)
- L76 `AwaitingPaymentListTests` (class) — Delivered cash-on-delivery orders nobody marked paid are called out.
- L79 `setUp(self)` (method)
- L96 `test_the_list_says_how_many_are_waiting(self)` (method)
- L100 `test_the_filter_shows_only_those_orders(self)` (method)

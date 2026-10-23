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

# plugins/installed/orders/tests/test_refunds.py

Symbols in `plugins/installed/orders/tests/test_refunds.py`.

- L19 `_setup_order(amount='25', qty=2)` (function)
- L46 `_succeeded_stripe_tx(order)` (function) — Give the order a successful Stripe transaction so a gateway refund
- L60 `RefundServiceTests` (class)
- L61 `test_gateway_backed_refund_moves_money_and_marks_processed(self)` (method)
- L77 `test_no_transaction_leaves_refund_unprocessed(self)` (method)
- L85 `test_over_refund_is_rejected(self)` (method)
- L95 `test_process_is_idempotent(self)` (method)
- L101 `test_gateway_success_fires_payment_refunded_once(self)` (method)
- L126 `ReturnRequestTests` (class)
- L127 `test_create_assigns_rma_number(self)` (method)
- L137 `test_approve_computes_refund_amount(self)` (method)
- L148 `test_full_flow_to_refunded(self)` (method)
- L161 `RefundAgentToolsTests` (class)
- L162 `test_tools_registered(self)` (method)

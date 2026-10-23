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

# plugins/installed/loyalty_points/tests/test_redeem_checkout.py

Symbols in `plugins/installed/loyalty_points/tests/test_redeem_checkout.py`.

- L47 `_grant(customer, points)` (function) — Give a customer a starting balance (an earn row).
- L52 `LoyaltyDebitLedgerTests` (class) — The idempotent debit / reversal helpers, in isolation.
- L55 `setUp(self)` (method)
- L59 `_order(self)` (method)
- L67 `test_debit_writes_one_negative_txn(self)` (method)
- L78 `test_debit_is_idempotent(self)` (method)
- L90 `test_reversal_credits_back(self)` (method)
- L96 `test_reversal_is_idempotent(self)` (method)
- L109 `test_reversal_noop_when_nothing_spent(self)` (method)
- L115 `LoyaltyCheckoutIntegrationTests` (class) — The real checkout path debits, and cancel reverses.
- L118 `setUp(self)` (method)
- L132 `_cart_with_points(self, redeem)` (method)
- L141 `test_checkout_with_points_debits_ledger(self)` (method)
- L155 `test_checkout_without_points_leaves_balance(self)` (method)
- L165 `test_cancel_reverses_points(self)` (method)
- L178 `LoyaltyApplyEndpointTests` (class) — The /checkout/points/apply|remove/ endpoints (owned by the plugin).
- L181 `setUp(self)` (method)
- L188 `_cart_key(self)` (method)
- L192 `test_apply_requires_auth(self)` (method)
- L197 `test_apply_sets_clamped_metadata(self)` (method)
- L202 `test_apply_clamps_to_balance(self)` (method)
- L207 `test_remove_clears(self)` (method)

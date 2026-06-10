---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/fraud_rules/tests/test_scoring.py

Symbols in `plugins/installed/fraud_rules/tests/test_scoring.py`.

- L27 `_FakeMoney` (class) — Stand-in for djmoney Money — `total.amount` access pattern.
- L30 `__init__(self, amount)` (method)
- L34 `_FakeOrder` (class) — Minimal order shape that score_order reads from.
- L37 `__init__(self, *, pk='order-1', order_number='X-1', customer_id=None, customer_email='', metadata=None, total=Decimal('100'), shipping_address=None, billing_address=None)` (method)
- L59 `BucketBoundaryTests` (class) — The thresholds are the system's contract with the merchant.
- L62 `test_zero_is_ok(self)` (method)
- L65 `test_below_watch_is_ok(self)` (method)
- L68 `test_watch_starts_at_30(self)` (method)
- L72 `test_review_starts_at_60(self)` (method)
- L76 `test_reject_starts_at_80(self)` (method)
- L81 `AddressMismatchTests` (class)
- L82 `test_same_country_no_flag(self)` (method)
- L90 `test_different_country_flags(self)` (method)
- L101 `test_case_insensitive(self)` (method)
- L109 `test_empty_addresses_no_flag(self)` (method)
- L115 `BinDenylistTests` (class)
- L116 `test_no_denylist_no_flag(self)` (method)
- L125 `test_matching_bin_flags(self)` (method)
- L135 `test_non_matching_bin_no_flag(self)` (method)
- L145 `CombinedRulesTests` (class) — When multiple rules trigger, their points sum (capped at 100).
- L148 `test_address_mismatch_plus_bin(self)` (method)
- L165 `test_score_capped_at_100(self)` (method) — When points add up beyond 100, they clamp.
- L196 `ScoreOrderFailSafeTests` (class) — score_order MUST NOT raise — the order pipeline depends on it.
- L199 `test_internal_exception_returns_safe_result(self)` (method)
- L214 `NewCustomerHighValueTests` (class) — First-order + high-value rule (+10).
- L217 `_run_with_safe_db_rules(self, order)` (method) — Patch every rule that touches the real ORM so only the
- L234 `test_new_customer_high_value_flags(self)` (method)
- L251 `test_low_value_first_order_no_flag(self)` (method)

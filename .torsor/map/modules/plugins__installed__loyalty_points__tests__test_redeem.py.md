---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/loyalty_points/tests/test_redeem.py

Symbols in `plugins/installed/loyalty_points/tests/test_redeem.py`.

- L21 `_make_user(email: str, password: str='pw')` (function)
- L29 `RedemptionMathTests` (class) — Pure helpers — no DB needed beyond the default rate.
- L32 `test_points_to_amount_default_rate(self)` (method)
- L39 `test_points_to_amount_rounds_down(self)` (method)
- L45 `test_amount_to_points_rounds_up(self)` (method)
- L52 `test_negative_points_floor_at_zero(self)` (method)
- L58 `RedeemServiceTests` (class)
- L59 `setUp(self)` (method)
- L65 `test_redeem_records_negative_txn_and_returns_money(self)` (method)
- L79 `test_redeem_more_than_balance_raises(self)` (method)
- L85 `test_redeem_non_positive_raises(self)` (method)
- L91 `test_reverse_redemption_recredits(self)` (method)
- L103 `test_max_redeemable_caps_at_order_value(self)` (method)
- L113 `_FakeCart` (class) — Minimal cart stand-in for the breakdown hook contract test.
- L116 `__init__(self, customer, redeem)` (method)
- L121 `BreakdownHookTests` (class)
- L122 `setUp(self)` (method)
- L131 `_breakdown(self, total='10.00')` (method)
- L142 `test_hook_applies_capped_points_discount(self)` (method)
- L150 `test_hook_caps_at_order_total(self)` (method)
- L157 `test_hook_noop_without_redeem_metadata(self)` (method)
- L164 `AccountPointsBoundaryTests` (class) — Boundary triplet for the customer-scoped /account/points/ view.
- L172 `setUp(self)` (method)
- L180 `test_anon_redirected_to_login(self)` (method)
- L185 `test_owner_sees_own_balance(self)` (method)
- L194 `test_other_customer_does_not_see_first_customers_points(self)` (method)

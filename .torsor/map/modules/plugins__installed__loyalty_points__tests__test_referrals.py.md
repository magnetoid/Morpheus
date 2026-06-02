---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/loyalty_points/tests/test_referrals.py

Symbols in `plugins/installed/loyalty_points/tests/test_referrals.py`.

- L25 `_FakeMoney` (class)
- L26 `__init__(self, amount)` (method)
- L30 `_FakeOrder` (class)
- L31 `__init__(self, *, customer_id, total, order_number='X-1')` (method)
- L37 `ReferralCodeTests` (class)
- L38 `test_first_call_mints_persistent_code(self)` (method)
- L55 `test_existing_code_is_returned_unchanged(self)` (method)
- L67 `RecordReferralTests` (class)
- L68 `setUp(self)` (method)
- L84 `test_invalid_code_no_op(self)` (method)
- L88 `test_empty_code_no_op(self)` (method)
- L92 `test_self_referral_blocked(self)` (method)
- L97 `QualifyOnOrderTests` (class)
- L98 `setUp(self)` (method)
- L117 `test_below_threshold_does_not_qualify(self)` (method)
- L127 `test_above_threshold_qualifies_and_mints_both_rewards(self)` (method)
- L150 `test_already_rewarded_referral_no_double_mint(self)` (method)
- L160 `test_no_pending_referral_no_op(self)` (method)
- L169 `test_missing_customer_id_no_op(self)` (method)

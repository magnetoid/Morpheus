---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/subscriptions/tests/test_stripe_adapter.py

Symbols in `plugins/installed/subscriptions/tests/test_stripe_adapter.py`.

- L30 `_plan(**kw)` (function)
- L43 `_customer(**kw)` (function)
- L49 `SyncPlanTests` (class)
- L50 `setUp(self)` (method)
- L55 `test_creates_and_stores_price_when_blank(self)` (method)
- L75 `test_idempotent_when_already_synced(self)` (method)
- L87 `test_zero_decimal_currency_sends_whole_units(self)` (method)
- L100 `SyncPlanProviderTests` (class)
- L101 `test_manual_plan_returns_empty_without_stripe_call(self)` (method)
- L112 `test_missing_key_fails_soft(self)` (method)
- L125 `StartSubscriptionTests` (class)
- L126 `setUp(self)` (method)
- L134 `_fake_stripe_sub(self, **kw)` (method)
- L144 `test_happy_path_ensures_customer_and_stores_provider_and_periods(self)` (method)
- L186 `test_trial_days_forwarded_and_state_mapped(self)` (method)
- L206 `test_period_read_from_subscription_items_fallback(self)` (method)
- L228 `test_stripe_error_returns_success_false_no_crash(self)` (method)
- L246 `test_missing_key_fails_soft(self)` (method)
- L258 `CancelPauseResumeTests` (class)
- L259 `setUp(self)` (method)
- L272 `test_cancel_at_period_end_mirrors_flag(self)` (method)
- L282 `test_cancel_immediately_deletes_and_marks_cancelled(self)` (method)
- L292 `test_cancel_stripe_error_does_not_mirror(self)` (method)
- L300 `test_pause_then_resume(self)` (method)

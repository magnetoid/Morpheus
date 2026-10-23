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

# plugins/installed/subscriptions/tests/test_billing_drips.py

Symbols in `plugins/installed/subscriptions/tests/test_billing_drips.py`.

- L26 `_Base` (class)
- L27 `setUp(self)` (method)
- L35 `_consent(self, marketing=True)` (method)
- L38 `_sub(self, **kw)` (method)
- L47 `_past_due(self, *, anchor_days_ago=0, sent=None)` (method)
- L53 `_active(self, *, period_end_in_days, **kw)` (method)
- L58 `DunningTests` (class)
- L60 `test_step0_sends_once_and_not_again_same_day(self, send)` (method)
- L75 `test_step1_due_after_three_days(self, send)` (method)
- L85 `test_no_send_without_marketing_consent(self, send)` (method)
- L91 `test_consent_false_blocks_send(self, send)` (method)
- L98 `test_non_past_due_subscription_is_skipped(self, send)` (method)
- L108 `test_anchor_falls_back_to_open_invoice(self, send)` (method)
- L124 `PreRenewalTests` (class)
- L126 `test_sends_once_per_period(self, send)` (method)
- L140 `test_skips_outside_prerenewal_window(self, send)` (method)
- L147 `test_new_period_reminds_again(self, send)` (method)
- L161 `test_cancelling_subscription_gets_no_reminder(self, send)` (method)
- L168 `test_respects_consent(self, send)` (method)

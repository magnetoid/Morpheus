---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/cart_abandonment/tests/test_recovery_drip.py

Symbols in `plugins/installed/cart_abandonment/tests/test_recovery_drip.py`.

- L24 `CartRecoveryDripTests` (class)
- L25 `setUp(self)` (method)
- L39 `_cart(self, *, customer=None, with_item=True, age_minutes=None, metadata=None)` (method)
- L56 `_consent(self, marketing: bool)` (method)
- L59 `_run(self)` (method)
- L64 `_scan(self)` (method)
- L69 `_set_abandoned_emitted(self, cart, *, minutes_ago: int)` (method) — Backdate the cart's 'abandoned_emitted' anchor without touching
- L79 `test_step1_does_not_send_before_delay(self)` (method)
- L85 `test_step1_sends_once_when_due(self)` (method)
- L95 `test_step2_only_after_delay2(self)` (method)
- L112 `test_rerun_does_not_resend(self)` (method)
- L126 `test_scan_then_drip_step1_still_fires(self)` (method) — Detection (scan_abandoned_carts) bumped Cart.updated_at via auto_now,
- L157 `test_extra_delay_without_template_never_sends(self)` (method) — step_delays_minutes can be longer than the 3 defined templates. A 4th
- L184 `test_no_email_without_marketing_consent(self)` (method)
- L190 `test_no_email_with_no_consent_row(self)` (method)
- L196 `test_email_with_marketing_consent_true(self)` (method)
- L202 `test_latest_consent_row_wins(self)` (method)
- L212 `test_empty_cart_gets_no_email(self)` (method)
- L220 `test_consent_not_required_sends_without_a_row(self)` (method)
- L235 `test_recovery_disabled_sends_nothing(self)` (method)
- L250 `SingleSenderInvariantTests` (class) — (f) Exactly one recovery-email code path remains.
- L258 `test_core_emails_no_longer_registers_cart_abandoned(self)` (method)
- L263 `test_marketing_no_longer_has_recovery_task(self)` (method)
- L268 `test_marketing_plugin_no_longer_handles_cart_abandoned(self)` (method)
- L273 `test_registered_cart_abandoned_handlers_exclude_retired_senders(self)` (method)

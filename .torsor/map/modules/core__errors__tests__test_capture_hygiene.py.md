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

# core/errors/tests/test_capture_hygiene.py

Symbols in `core/errors/tests/test_capture_hygiene.py`.

- L34 `SecretRedactionTests` (class)
- L35 `test_a_message_never_stores_a_key_or_token(self)` (method)
- L43 `test_an_exception_and_its_traceback_never_store_a_key(self)` (method)
- L51 `test_a_password_in_a_url_or_setting_is_removed(self)` (method)
- L61 `BrowserNoiseTests` (class)
- L62 `test_every_aborted_page_transition_is_noise(self)` (method)
- L68 `test_an_opaque_cross_origin_error_is_noise(self)` (method)
- L72 `test_a_real_error_is_not_noise(self)` (method)
- L76 `StaleGroupTests` (class)
- L77 `_event(self, fp, days_ago)` (method)
- L83 `test_a_group_quiet_for_two_weeks_is_resolved_and_a_recent_one_stays_open(self)` (method)
- L96 `test_the_nightly_prune_resolves_stale_groups(self)` (method)
- L104 `JanusFailureLevelTests` (class)
- L105 `test_a_turn_that_gives_no_reply_is_logged_as_an_error(self)` (method)

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

# plugins/installed/consent/tests/test_server_side_consent.py

Symbols in `plugins/installed/consent/tests/test_server_side_consent.py`.

- L25 `_set_gdpr(on: bool)` (function)
- L34 `_request(**flags)` (function)
- L41 `_order(**consent)` (function)
- L45 `DecisionTests` (class)
- L46 `setUp(self)` (method)
- L49 `test_a_managed_store_with_no_cookie_grants_nothing(self)` (method)
- L54 `test_the_cookie_answers_per_category(self)` (method)
- L58 `test_no_request_means_no_visitor_and_nothing_granted(self)` (method)
- L63 `test_global_privacy_control_is_a_refusal(self)` (method)
- L68 `test_a_store_with_gdpr_off_is_unmanaged(self)` (method)
- L73 `test_with_the_consent_app_off_nothing_answers_and_the_store_is_unmanaged(self)` (method)
- L81 `test_stamp_is_the_decision(self)` (method)
- L84 `test_an_unknown_category_is_a_programming_error(self)` (method)
- L89 `OrderStampTests` (class)
- L90 `setUp(self)` (method)
- L93 `test_the_stamp_beats_the_request(self)` (method)
- L97 `test_a_stamped_yes_is_allowed(self)` (method)
- L100 `test_an_order_stamped_unmanaged_is_allowed(self)` (method)
- L103 `test_an_unstamped_order_on_a_managed_store_is_refused(self)` (method)
- L106 `test_an_unstamped_order_on_an_unmanaged_store_is_allowed(self)` (method)
- L110 `test_a_stamped_no_still_refuses_after_management_is_switched_off(self)` (method)
- L118 `MarketingCustomersTests` (class)
- L119 `setUp(self)` (method)
- L135 `test_only_the_latest_yes_counts(self)` (method)
- L138 `test_an_unmanaged_store_has_no_restriction(self)` (method)

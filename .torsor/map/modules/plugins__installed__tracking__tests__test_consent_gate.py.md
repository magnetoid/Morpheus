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

# plugins/installed/tracking/tests/test_consent_gate.py

Symbols in `plugins/installed/tracking/tests/test_consent_gate.py`.

- L29 `_set_gdpr(on: bool)` (function)
- L38 `_order(consent, product=None)` (function)
- L53 `Ga4ConsentTests` (class)
- L54 `setUp(self)` (method)
- L65 `test_a_visitor_with_no_decision_sends_no_view_item(self)` (method)
- L71 `test_a_visitor_who_accepted_analytics_sends_view_item(self)` (method)
- L77 `test_purchase_follows_the_orders_stamp(self)` (method)
- L86 `test_the_debug_override_still_sends(self)` (method)
- L98 `test_an_unmanaged_store_sends_as_before(self)` (method)
- L105 `AdsTagConsentTests` (class)
- L106 `setUp(self)` (method)
- L114 `_render(self, consent)` (method)
- L122 `test_no_tag_without_marketing_consent(self)` (method)
- L125 `test_tag_with_marketing_consent(self)` (method)
- L128 `test_tag_on_a_store_without_the_consent_app(self)` (method)
- L132 `OneBannerTests` (class)
- L133 `test_the_retired_banner_tag_renders_nothing(self)` (method)
- L140 `test_no_theme_renders_it(self)` (method)

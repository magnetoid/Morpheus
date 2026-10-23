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

# plugins/tests_capi_consent.py

Symbols in `plugins/tests_capi_consent.py`.

- L66 `_set_gdpr(on: bool)` (function)
- L75 `_order(consent=None)` (function)
- L79 `_request(marketing=None)` (function)
- L86 `PurchaseConsentTests` (class)
- L87 `setUp(self)` (method)
- L90 `_sent(self, app, path, order)` (method)
- L95 `test_a_stamped_no_sends_nothing(self)` (method)
- L102 `test_a_stamped_yes_sends(self)` (method)
- L107 `test_an_unstamped_order_on_a_managed_store_sends_nothing(self)` (method)
- L112 `test_a_store_that_does_not_manage_consent_sends_as_before(self)` (method)
- L118 `test_a_real_paid_order_fired_through_the_bus_respects_its_stamp(self)` (method)
- L135 `CartEventConsentTests` (class)
- L136 `setUp(self)` (method)
- L139 `_sent(self, app, handler, path, arg, request)` (method)
- L144 `test_a_visitor_who_refused_is_not_sent(self)` (method)
- L149 `test_a_visitor_who_accepted_is_sent(self)` (method)
- L154 `test_an_unmanaged_store_sends_as_before(self)` (method)
- L161 `CartFiresCarryTheRequestTests` (class)
- L162 `test_add_to_cart_passes_the_request(self)` (method)

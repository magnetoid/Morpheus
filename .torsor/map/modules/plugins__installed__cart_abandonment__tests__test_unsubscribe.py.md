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

# plugins/installed/cart_abandonment/tests/test_unsubscribe.py

Symbols in `plugins/installed/cart_abandonment/tests/test_unsubscribe.py`.

- L32 `RecoveryTokenTests` (class)
- L33 `test_token_round_trips_and_normalises_case(self)` (method)
- L37 `test_forged_token_returns_none(self)` (method)
- L40 `test_headers_are_the_rfc8058_pair(self)` (method)
- L46 `test_suppress_from_token_is_idempotent(self)` (method)
- L55 `RecoveryUnsubscribeViewTests` (class)
- L56 `test_one_click_post_unsubscribes_without_csrf(self)` (method)
- L62 `test_footer_link_get_unsubscribes(self)` (method)
- L68 `test_forged_token_is_404(self)` (method)
- L74 `RecoveryDripUnsubscribeTests` (class)
- L75 `setUp(self)` (method)
- L80 `_guest_cart(self, *, email='shopper@example.test', age_minutes=90, session='sess-u')` (method)
- L90 `_consent(self, session='sess-u', marketing=True)` (method)
- L93 `test_drip_carries_list_unsubscribe_header_and_footer(self)` (method)
- L105 `test_suppressed_address_is_never_dripped(self)` (method)

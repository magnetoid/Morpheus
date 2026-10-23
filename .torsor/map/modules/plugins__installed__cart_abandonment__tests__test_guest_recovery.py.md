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

# plugins/installed/cart_abandonment/tests/test_guest_recovery.py

Symbols in `plugins/installed/cart_abandonment/tests/test_guest_recovery.py`.

- L25 `GuestRecoveryTests` (class)
- L26 `setUp(self)` (method)
- L35 `_guest_cart(self, *, email='guest@example.test', age_minutes=90, session='sess-1')` (method)
- L46 `_consent(self, session='sess-1', marketing=True)` (method)
- L49 `test_scanner_fires_for_guest_with_stamped_email(self)` (method)
- L58 `test_scanner_still_skips_guest_without_email(self)` (method)
- L65 `test_drip_reaches_consented_guest(self)` (method)
- L76 `test_drip_never_emails_guest_without_consent(self)` (method)
- L87 `test_drip_respects_guest_opt_out(self)` (method)

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

# plugins/installed/storefront/tests/test_withdrawal_waiver.py

Symbols in `plugins/installed/storefront/tests/test_withdrawal_waiver.py`.

- L36 `_product(slug, *, requires_shipping)` (function)
- L47 `_cart_with(*products)` (function)
- L54 `_request(cart_id, **post)` (function)
- L60 `CartDigitalDetectionTests` (class)
- L61 `test_digital_item_detected(self)` (method)
- L65 `test_physical_only_not_digital(self)` (method)
- L69 `test_mixed_cart_is_digital(self)` (method)
- L76 `test_no_cart_not_digital(self)` (method)
- L81 `WaiverGateTests` (class)
- L82 `test_digital_cart_unticked_is_blocked(self, _mock)` (method)
- L86 `test_digital_cart_ticked_passes(self, _mock)` (method)
- L90 `test_physical_cart_never_gated(self, _mock)` (method)
- L94 `test_disabled_waiver_never_gates(self, mock)` (method)
- L100 `WaiverConfigAndRecordTests` (class)
- L101 `test_default_config_is_off_with_text(self)` (method)
- L106 `test_record_stamps_order_metadata(self)` (method)
- L122 `test_record_noop_on_empty_order_no(self)` (method)

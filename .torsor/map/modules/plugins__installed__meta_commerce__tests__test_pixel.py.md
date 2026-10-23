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

# plugins/installed/meta_commerce/tests/test_pixel.py

Symbols in `plugins/installed/meta_commerce/tests/test_pixel.py`.

- L16 `_plugin()` (function)
- L33 `_enable(pixel_id='123456789012345')` (function)
- L40 `PixelTests` (class)
- L41 `setUp(self)` (method)
- L44 `tearDown(self)` (method)
- L47 `_ctx(self, path='/', product=None)` (method)
- L53 `test_disabled_by_default(self)` (method)
- L56 `test_invalid_pixel_id_renders_nothing(self)` (method)
- L60 `test_enabled_emits_fbq(self)` (method)
- L67 `test_pdp_emits_viewcontent_with_content_ids(self)` (method)
- L82 `test_purchase_fires_on_confirmation_with_dedup_event_id(self)` (method)
- L116 `test_purchase_does_not_fire_off_confirmation_path(self)` (method)
- L122 `test_malicious_sku_cannot_break_out(self)` (method)

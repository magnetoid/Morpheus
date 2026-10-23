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

# plugins/installed/google_shopping/tests/test_remarketing.py

Symbols in `plugins/installed/google_shopping/tests/test_remarketing.py`.

- L16 `_ctx(path='/')` (function)
- L20 `_gs_plugin()` (function) — The registry's live plugin instance — the one feed_settings() reads.
- L38 `_enable(cid='AW-123456789')` (function)
- L45 `_CacheIsolation` (class) — The registry plugin instance is long-lived across the whole test run, so
- L51 `setUp(self)` (method)
- L54 `tearDown(self)` (method)
- L58 `RemarketingGatingTests` (class)
- L59 `test_disabled_by_default_renders_nothing(self)` (method)
- L62 `test_enabled_without_id_renders_nothing(self)` (method)
- L68 `test_invalid_id_renders_nothing(self)` (method)
- L72 `test_enabled_emits_gtag(self)` (method)
- L80 `RemarketingPayloadTests` (class)
- L81 `setUp(self)` (method)
- L85 `test_product_page_carries_prodid_and_value(self)` (method)
- L100 `test_xss_safe_id_is_regex_gated(self)` (method)
- L105 `test_malicious_sku_cannot_break_out_of_script(self)` (method)

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

# plugins/installed/tracking/views.py

Symbols in `plugins/installed/tracking/views.py`.

- L52 `_stats()` (function) — Cheap summary for the overview page.
- L79 `overview(request)` (function)
- L102 `settings_page(request)` (function) — Comprehensive control center. Tab strip across the top; each
- L229 `event_log(request)` (function)
- L252 `event_detail(request, event_id)` (function)
- L315 `test_purchase(request)` (function) — Back-compat shim around test_event for the legacy 'send test
- L323 `test_event(request, event_name: str='purchase')` (function) — Fire one synthetic GA4 event so the merchant can verify the
- L361 `connection_check(request)` (function) — Probe the GA4 Measurement Protocol *debug* endpoint with the
- L442 `gtm_container_export(request)` (function) — Serve a pre-built GTM container JSON ready for the merchant to

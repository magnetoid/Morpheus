---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/tracking/views.py

Symbols in `plugins/installed/tracking/views.py`.

- L51 `_stats()` (function) — Cheap summary for the overview page.
- L77 `overview(request)` (function)
- L99 `settings_page(request)` (function) — Comprehensive control center. Tab strip across the top; each
- L231 `event_log(request)` (function)
- L253 `event_detail(request, event_id)` (function)
- L315 `test_purchase(request)` (function) — Back-compat shim around test_event for the legacy 'send test
- L322 `test_event(request, event_name: str='purchase')` (function) — Fire one synthetic GA4 event so the merchant can verify the
- L359 `connection_check(request)` (function) — Probe the GA4 Measurement Protocol *debug* endpoint with the
- L439 `gtm_container_export(request)` (function) — Serve a pre-built GTM container JSON ready for the merchant to

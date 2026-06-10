---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/shipping/dashboard.py

Symbols in `plugins/installed/shipping/dashboard.py`.

- L21 `_trail(*items)` (function)
- L31 `_parse_csv(raw: str)` (function) — Split 'US, CA, *' into ['US', 'CA', '*'].
- L36 `_create_zone(request)` (function)
- L55 `_edit_zone(request, zone_id: str)` (function)
- L72 `_delete_zone(request, zone_id: str)` (function)
- L84 `_load_config()` (function) — Carrier config as the quote path sees it (PluginConfig.config).
- L91 `_save_config(request)` (function) — Persist carrier credentials + the tax-on-shipping flag to the shipping
- L126 `zones(request)` (function) — Unified Shipping settings — zones + rates on ONE page (ADR 0003: no
- L202 `_create_rate(request)` (function)
- L228 `_edit_rate(request, rate_id: str)` (function)
- L258 `_delete_rate(request, rate_id: str)` (function)
- L271 `rates(request)` (function) — Back-compat redirect: rates merged into the unified Shipping page

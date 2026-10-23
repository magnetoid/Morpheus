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

# plugins/installed/shipping/dashboard.py

Symbols in `plugins/installed/shipping/dashboard.py`.

- L24 `_trail(*items)` (function)
- L28 `_parse_csv(raw: str)` (function) — Split 'US, CA, *' into ['US', 'CA', '*'].
- L33 `_create_zone(request)` (function)
- L52 `_edit_zone(request, zone_id: str)` (function)
- L69 `_delete_zone(request, zone_id: str)` (function)
- L81 `_load_config()` (function) — Carrier config as the quote path sees it (PluginConfig.config).
- L88 `_save_config(request)` (function) — Persist carrier credentials + the tax-on-shipping flag to the shipping
- L124 `zones(request)` (function) — Unified Shipping settings — zones + rates on ONE page (ADR 0003: no
- L200 `_create_rate(request)` (function)
- L226 `_edit_rate(request, rate_id: str)` (function)
- L256 `_delete_rate(request, rate_id: str)` (function)
- L270 `rates(request)` (function) — Back-compat redirect: rates merged into the unified Shipping page

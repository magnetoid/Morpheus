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

# plugins/installed/dynamics/app.py

Symbols in `plugins/installed/dynamics/app.py`.

- L63 `DynamicsPlugin` (class)
- L76 `ready(self)` (method)
- L126 `on_product_viewed(self, product=None, request=None, **kwargs)` (method) — Maintain session['recently_viewed'] (idempotent, capped).
- L149 `on_order_placed(self, order=None, **kwargs)` (method) — After a sale, debounce a probability refresh so the grid reflects the
- L162 `contribute_storefront_blocks(self)` (method)
- L177 `contribute_dashboard_pages(self)` (method)
- L203 `get_config_schema(self)` (method)
- L221 `contribute_settings_panel(self)` (method)

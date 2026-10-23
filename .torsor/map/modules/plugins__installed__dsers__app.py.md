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

# plugins/installed/dsers/app.py

Symbols in `plugins/installed/dsers/app.py`.

- L28 `DsersPlugin` (class)
- L39 `ready(self)` (method)
- L51 `contribute_dashboard_pages(self)` (method)
- L64 `contribute_settings_panel(self)` (method)
- L72 `get_config_schema(self)` (method)
- L103 `_rows_for(product)` (method) — One row per variant (or one for the product when it has none).
- L130 `on_product_form_cards(self, value, product=None, **kwargs)` (method)
- L142 `on_product_form_saved(self, product=None, post=None, **kwargs)` (method)
- L163 `on_order_cancelled(self, order=None, **kwargs)` (method) — An order cancelled after it went to DSers must be cancelled there too.

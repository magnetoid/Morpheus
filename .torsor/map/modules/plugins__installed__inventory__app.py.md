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

# plugins/installed/inventory/app.py

Symbols in `plugins/installed/inventory/app.py`.

- L7 `InventoryPlugin` (class)
- L15 `ready(self)` (method)
- L81 `on_dashboard_panels(self, value, date_range=None, **kwargs)` (method) — Fold the low-stock list (+ threshold) into the home context.
- L103 `on_stock_summary(self, value=None, product_ids=None, **kwargs)` (method) — PRODUCT_STOCK_SUMMARY: add this app's stock answer for ``product_ids``.
- L111 `reserve_stock_filter(self, value=0, order=None, **kwargs)` (method)
- L121 `on_order_paid(self, order, **kwargs)` (method)
- L127 `on_order_cancelled(self, order, **kwargs)` (method)
- L133 `on_return_refunded(self, return_request=None, **kwargs)` (method) — Restock the variant rows for items in a refunded return —
- L152 `contribute_dashboard_cards(self)` (method)
- L167 `contribute_dashboard_pages(self)` (method)
- L182 `contribute_agent_tools(self)` (method)
- L199 `contribute_skills(self)` (method) — The Inventory skill — opt in via skills=['inventory'] for stock

---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/inventory/plugin.py

Symbols in `plugins/installed/inventory/plugin.py`.

- L6 `InventoryPlugin` (class)
- L14 `ready(self)` (method)
- L64 `on_dashboard_panels(self, value, date_range=None, **kwargs)` (method) — Fold the low-stock list (+ threshold) into the home context.
- L87 `on_order_placed(self, order, **kwargs)` (method)
- L93 `on_order_paid(self, order, **kwargs)` (method)
- L99 `on_order_cancelled(self, order, **kwargs)` (method)
- L105 `on_return_refunded(self, return_request=None, **kwargs)` (method) — Restock the variant rows for items in a refunded return —
- L124 `contribute_dashboard_pages(self)` (method)
- L138 `contribute_agent_tools(self)` (method)
- L155 `contribute_skills(self)` (method) — The Inventory skill — opt in via skills=['inventory'] for stock

---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/inventory/plugin.py

Symbols in `plugins/installed/inventory/plugin.py`.

- L4 `InventoryPlugin` (class)
- L12 `ready(self)` (method)
- L52 `on_order_placed(self, order, **kwargs)` (method)
- L58 `on_order_paid(self, order, **kwargs)` (method)
- L64 `on_order_cancelled(self, order, **kwargs)` (method)
- L70 `on_return_refunded(self, return_request=None, **kwargs)` (method) — Restock the variant rows for items in a refunded return —
- L89 `contribute_agent_tools(self)` (method)
- L104 `contribute_skills(self)` (method) — The Inventory skill — opt in via skills=['inventory'] for stock

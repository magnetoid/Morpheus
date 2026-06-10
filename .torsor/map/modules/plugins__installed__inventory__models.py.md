---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/inventory/models.py

Symbols in `plugins/installed/inventory/models.py`.

- L11 `Warehouse` (class)
- L23 `__str__(self)` (method)
- L27 `StockLevel` (class) — Current stock per variant per warehouse.
- L43 `__str__(self)` (method)
- L47 `available_quantity(self)` (method)
- L51 `is_low_stock(self)` (method)
- L55 `is_out_of_stock(self)` (method)
- L59 `StockMovement` (class) — Audit log of every stock change.
- L88 `__str__(self)` (method)
- L92 `record(cls, stock_level, movement_type, quantity_change, reference='', notes='', user=None)` (method) — Atomically update stock and record movement.
- L111 `BackInStockSubscription` (class) — Email me when this product is back in stock.

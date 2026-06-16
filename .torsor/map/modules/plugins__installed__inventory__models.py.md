---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/inventory/models.py

Symbols in `plugins/installed/inventory/models.py`.

- L14 `Warehouse` (class)
- L26 `__str__(self)` (method)
- L30 `StockLevel` (class) — Current stock per variant per warehouse.
- L47 `__str__(self)` (method)
- L51 `available_quantity(self)` (method)
- L55 `is_low_stock(self)` (method)
- L59 `is_out_of_stock(self)` (method)
- L63 `StockMovement` (class) — Audit log of every stock change.
- L95 `__str__(self)` (method)
- L99 `record(cls, stock_level, movement_type, quantity_change, reference='', notes='', user=None)` (method) — Atomically update stock and record movement.
- L118 `BackInStockSubscription` (class) — Email me when this product is back in stock.
- L154 `StockoutAlert` (class) — An open episode where a variant is projected to stock out within the
- L185 `__str__(self)` (method)

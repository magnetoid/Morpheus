---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/inventory/services.py

Symbols in `plugins/installed/inventory/services.py`.

- L30 `InsufficientStockError` (class) — Raised when a reservation would exceed available_quantity.
- L34 `InventoryService` (class)
- L36 `available(cls, variant)` (method) — Total reservable units across all warehouses for one variant.
- L41 `is_in_stock(cls, variant, qty: int=1)` (method)
- L45 `reserve_for_order(cls, order)` (method) — Reserve stock for every order item that points at a tracked variant.
- L115 `release_reservation(cls, order)` (method) — Undo the reservations made by `reserve_for_order`.
- L157 `commit_for_order(cls, order)` (method) — Convert reservations into actual stock decrements (after payment).
- L209 `restock_for_return(cls, return_request)` (method) — Add stock back when a return is refunded. Idempotent: a
- L269 `_qty_from_note(note: str)` (function) — Parse `Reserved 2× for ABC` style notes back to the qty.

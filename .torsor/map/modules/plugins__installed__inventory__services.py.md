---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/inventory/services.py

Symbols in `plugins/installed/inventory/services.py`.

- L30 `InsufficientStockError` (class) — Raised when a reservation would exceed available_quantity.
- L34 `InventoryService` (class)
- L37 `available(cls, variant)` (method) — Total reservable units across all warehouses for one variant.
- L45 `is_in_stock(cls, variant, qty: int=1)` (method)
- L49 `reserve_for_order(cls, order)` (method) — Reserve stock for every order item that points at a tracked variant.
- L118 `release_reservation(cls, order)` (method) — Undo the reservations made by `reserve_for_order`.
- L156 `commit_for_order(cls, order)` (method) — Convert reservations into actual stock decrements (after payment).
- L207 `restock_for_return(cls, return_request)` (method) — Add stock back when a return is refunded. Idempotent: a
- L265 `_qty_from_note(note: str)` (function) — Parse `Reserved 2× for ABC` style notes back to the qty.

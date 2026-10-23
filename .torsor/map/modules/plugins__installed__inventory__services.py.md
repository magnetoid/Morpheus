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

# plugins/installed/inventory/services.py

Symbols in `plugins/installed/inventory/services.py`.

- L30 `InsufficientStockError` (class) — Raised when a reservation would exceed available_quantity.
- L34 `InventoryService` (class)
- L36 `available(cls, variant)` (method) — Total reservable units across all warehouses for one variant.
- L41 `is_in_stock(cls, variant, qty: int=1)` (method)
- L45 `reserve_for_order(cls, order)` (method) — Reserve stock for every order item that points at a tracked variant.
- L136 `release_reservation(cls, order)` (method) — Undo the reservations made by `reserve_for_order`.
- L189 `commit_for_order(cls, order)` (method) — Convert reservations into actual stock decrements (after payment).
- L241 `restock_for_return(cls, return_request)` (method) — Add stock back when a return is refunded. Idempotent: a
- L301 `_qty_from_note(note: str)` (function) — Parse `Reserved 2× for ABC` style notes back to the qty.
- L323 `product_availability(product)` (function) — An availability token for ``product`` — the vocabulary key, not a URL.
- L354 `_is_unpriced(product)` (function) — No price to sell at: the product's own price is 0 and no active variant has one.
- L376 `_availability_from_stock(product_pk)` (function)
- L415 `variant_availability(variant)` (function) — An availability token for ONE variant.
- L445 `low_stock_threshold()` (function) — Units at or below which a product counts as low on stock — the number the
- L457 `stock_summary(product_ids)` (function) — Sellable units per product, for the ``PRODUCT_STOCK_SUMMARY`` filter.

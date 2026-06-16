---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/b2b/services_bulk_order.py

Symbols in `plugins/installed/b2b/services_bulk_order.py`.

- L43 `BulkOrderResult` (class)
- L50 `parse_csv(raw: str)` (function) — Parse the textarea / file content into [(row_number, sku, qty), ...].
- L96 `apply_to_cart(*, cart, parsed_rows: list[tuple[int, str, int]], account=None)` (function) — Materialise parsed rows into CartItem records on `cart`.

---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/inventory/graphql/mutations.py

Symbols in `plugins/installed/inventory/graphql/mutations.py`.

- L17 `StockMutationResult` (class)
- L26 `_is_staff(info)` (function)
- L34 `_check_scope(info, required: list[str])` (function)
- L49 `_err(msg: str)` (function)
- L56 `_resolve_variant(variant_sku: str, product_slug: str)` (function)
- L68 `_resolve_warehouse(name: str)` (function)
- L75 `_serialize_stock(s)` (function)
- L86 `SetStockInput` (class)
- L94 `AdjustStockInput` (class)
- L102 `InventoryMutationExtension` (class)
- L107 `set_stock(self, info: strawberry.Info, input: SetStockInput)` (method)
- L133 `adjust_stock(self, info: strawberry.Info, input: AdjustStockInput)` (method)

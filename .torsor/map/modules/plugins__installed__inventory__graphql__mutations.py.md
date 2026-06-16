---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/inventory/graphql/mutations.py

Symbols in `plugins/installed/inventory/graphql/mutations.py`.

- L18 `StockMutationResult` (class)
- L27 `_is_staff(info)` (function)
- L35 `_check_scope(info, required: list[str])` (function)
- L51 `_err(msg: str)` (function)
- L62 `_resolve_variant(variant_sku: str, product_slug: str)` (function)
- L75 `_resolve_warehouse(name: str)` (function)
- L83 `_serialize_stock(s)` (function)
- L95 `SetStockInput` (class)
- L103 `AdjustStockInput` (class)
- L111 `InventoryMutationExtension` (class)
- L115 `set_stock(self, info: strawberry.Info, input: SetStockInput)` (method)
- L143 `adjust_stock(self, info: strawberry.Info, input: AdjustStockInput)` (method)

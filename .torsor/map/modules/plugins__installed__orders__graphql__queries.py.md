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

# plugins/installed/orders/graphql/queries.py

Symbols in `plugins/installed/orders/graphql/queries.py`.

- L48 `_scoped_orders_qs(info: strawberry.Info)` (function) — Return an Order queryset scoped to what the caller is allowed to see.
- L65 `_resolve_cart(info: strawberry.Info, id=None)` (function) — Permission-checked cart lookup shared by the `cart` and `cartTotals`
- L105 `OrdersQueryExtension` (class)
- L107 `order(self, info: strawberry.Info, order_number: str)` (method)
- L114 `orders(self, info: strawberry.Info, first: int=50, order_by: str='-placed_at')` (method)
- L129 `cart(self, info: strawberry.Info, id: strawberry.ID | None=None)` (method)
- L137 `cart_totals(self, info: strawberry.Info, cart_id: strawberry.ID, address: AddressInput | None=None, shipping_rate_id: str | None=None)` (method)

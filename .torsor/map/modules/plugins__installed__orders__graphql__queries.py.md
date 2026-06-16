---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/orders/graphql/queries.py

Symbols in `plugins/installed/orders/graphql/queries.py`.

- L34 `_scoped_orders_qs(info: strawberry.Info)` (function) — Return an Order queryset scoped to what the caller is allowed to see.
- L52 `OrdersQueryExtension` (class)
- L54 `order(self, info: strawberry.Info, order_number: str)` (method)
- L61 `orders(self, info: strawberry.Info, first: int=50, order_by: str='-placed_at')` (method)
- L72 `cart(self, info: strawberry.Info, id: strawberry.ID | None=None)` (method)
- L116 `cart_totals(self, info: strawberry.Info, cart_id: strawberry.ID, address: AddressInput | None=None, shipping_rate_id: str | None=None)` (method)

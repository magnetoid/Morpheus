---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/orders/graphql/queries.py

Symbols in `plugins/installed/orders/graphql/queries.py`.

- L28 `_scoped_orders_qs(info: strawberry.Info)` (function) — Return an Order queryset scoped to what the caller is allowed to see.
- L50 `OrdersQueryExtension` (class)
- L53 `order(self, info: strawberry.Info, order_number: str)` (method)
- L60 `orders(self, info: strawberry.Info, first: int=50, order_by: str='-placed_at')` (method)
- L71 `cart(self, info: strawberry.Info, id: Optional[strawberry.ID]=None)` (method)
- L107 `cart_totals(self, info: strawberry.Info, cart_id: strawberry.ID, address: Optional[AddressInput]=None, shipping_rate_id: Optional[str]=None)` (method)

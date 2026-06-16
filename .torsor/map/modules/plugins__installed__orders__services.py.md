---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/orders/services.py

Symbols in `plugins/installed/orders/services.py`.

- L26 `CartService` (class)
- L28 `get_or_create_cart(cls, session_key: str='', customer=None)` (method)
- L36 `add_item(cls, cart: Cart, product_id: str, quantity: int=1, variant_id: str | None=None, currency: str | None=None)` (method) — Add a line item, picking the buyer-currency override if available.
- L113 `merge_carts(*, source_cart: Cart, target_cart: Cart)` (function) — Move items from ``source_cart`` into ``target_cart`` and delete the source.
- L142 `_is_inventoried(product, variant)` (function) — True when this product/variant tracks physical stock and should
- L167 `_resolve_unit_price(target, currency: str | None, *, fallback)` (function) — Return a ``Money`` honoring ``target.localized_prices[currency]``
- L192 `OrderService` (class)
- L194 `calculate_cart_breakdown(cls, *, cart: Cart, address: dict | None=None, billing_address: dict | None=None, shipping_rate_id: str='')` (method)
- L277 `create_from_cart(cls, cart: Cart, email: str, shipping_address: dict, billing_address: dict)` (method)
- L479 `confirm_order(cls, order: Order)` (method)

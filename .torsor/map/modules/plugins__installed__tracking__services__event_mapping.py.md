---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/tracking/services/event_mapping.py

Symbols in `plugins/installed/tracking/services/event_mapping.py`.

- L19 `_money_amount(value)` (function)
- L30 `_money_currency(value, default: str='USD')` (function)
- L37 `_product_item(product, *, quantity: int=1, variant=None, list_id: str='', list_name: str='', index: int=0)` (function) — Shape a Product (model OR dict) into a GA4 items[] entry.
- L90 `view_item(product)` (function)
- L103 `view_item_list(*, items: list, list_id: str='', list_name: str='')` (function)
- L117 `add_to_cart(*, cart, item, product, variant=None, quantity: int=1)` (function)
- L128 `remove_from_cart(*, cart, item, product, quantity: int=1)` (function)
- L137 `begin_checkout(cart)` (function)
- L164 `purchase(order)` (function)
- L206 `refund(*, order, amount=None)` (function)

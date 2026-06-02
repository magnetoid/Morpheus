---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:53'
updated: '2026-06-02T18:07:53'
---

# plugins/installed/tracking/services/event_mapping.py

Symbols in `plugins/installed/tracking/services/event_mapping.py`.

- L18 `_money_amount(value)` (function)
- L29 `_money_currency(value, default: str='USD')` (function)
- L36 `_product_item(product, *, quantity: int=1, variant=None, list_id: str='', list_name: str='', index: int=0)` (function) — Shape a Product (model OR dict) into a GA4 items[] entry.
- L79 `view_item(product)` (function)
- L88 `view_item_list(*, items: list, list_id: str='', list_name: str='')` (function)
- L100 `add_to_cart(*, cart, item, product, variant=None, quantity: int=1)` (function)
- L109 `remove_from_cart(*, cart, item, product, quantity: int=1)` (function)
- L118 `begin_checkout(cart)` (function)
- L142 `purchase(order)` (function)
- L179 `refund(*, order, amount=None)` (function)

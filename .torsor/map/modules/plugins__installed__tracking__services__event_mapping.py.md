---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/tracking/services/event_mapping.py

Symbols in `plugins/installed/tracking/services/event_mapping.py`.

- L19 `_money_amount(value)` (function)
- L30 `_money_currency(value, default: str='USD')` (function)
- L37 `_shown_price(product)` (function) — The price a shopper is shown for `product` (model OR dict).
- L62 `_product_item(product, *, quantity: int=1, variant=None, list_id: str='', list_name: str='', index: int=0, unit_price=None)` (function) — Shape a Product (model OR dict) into a GA4 items[] entry.
- L119 `view_item(product)` (function)
- L129 `view_item_list(*, items: list, list_id: str='', list_name: str='')` (function)
- L143 `add_to_cart(*, cart, item, product, variant=None, quantity: int=1)` (function)
- L155 `remove_from_cart(*, cart, item, product, quantity: int=1)` (function)
- L165 `begin_checkout(cart)` (function)
- L197 `purchase(order)` (function)
- L243 `refund(*, order, amount=None)` (function)

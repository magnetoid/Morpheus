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

# plugins/installed/orders/graphql/_ownership.py

Symbols in `plugins/installed/orders/graphql/_ownership.py`.

- L26 `_request_of(info)` (function)
- L31 `may_access_cart(info, cart)` (function) — True if the caller owns `cart` (or holds read:carts). Mirrors exactly the
- L47 `load_owned_cart(info, cart_id)` (function) — (cart, None) when the caller owns it; (None, ErrorType) otherwise.
- L60 `load_owned_item(info, item_id)` (function) — (item, None) when the caller owns the item's cart; (None, ErrorType) else.

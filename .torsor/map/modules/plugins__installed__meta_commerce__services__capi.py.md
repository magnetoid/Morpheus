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

# plugins/installed/meta_commerce/services/capi.py

Symbols in `plugins/installed/meta_commerce/services/capi.py`.

- L26 `_sha256(value: str)` (function)
- L30 `_send(event_name: str, *, value: float, currency: str, items, email='', event_id='')` (function) — Core CAPI sender. items = [(sku, qty)]. No-op when unconfigured.
- L55 `send_purchase(order)` (function) — Server-side Purchase event for `order`.
- L68 `send_add_to_cart(*, product=None, variant=None, quantity=1)` (function) — Server-side AddToCart — sharpens dynamic-ads/Advantage+ optimisation.
- L83 `send_initiate_checkout(cart)` (function) — Server-side InitiateCheckout from a cart.
- L89 `_log(res: dict, event_name: str='Purchase')` (function)

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

# plugins/installed/storefront/views/checkout_one_page.py

Symbols in `plugins/installed/storefront/views/checkout_one_page.py`.

- L47 `_fire_begin_checkout(request)` (function) — Fire BEGIN_CHECKOUT once per session (same flag as the legacy 3-step
- L75 `checkout_one_page(request)` (function) — Single-screen checkout — render or submit.
- L187 `_collect_address(request)` (function)
- L191 `_validate(addr: dict, *, no_shipping: bool)` (function)
- L210 `_shipping_input(addr: dict)` (function) — Map the storefront address form to GraphQL ``AddressInput`` fields.
- L231 `_submit_order(*, request, cart_id: str, addr: dict, rate_id: str, payment_method: str='')` (function)
- L266 `_redirect_to_confirmation(order_no: str)` (function)
- L286 `_render_form(request, *, addr: dict | None, rate_id: str, error: str, payment_method: str='')` (function)
- L314 `_payment_methods(request=None)` (function) — Enabled gateways for the checkout picker via CHECKOUT_GATEWAYS.

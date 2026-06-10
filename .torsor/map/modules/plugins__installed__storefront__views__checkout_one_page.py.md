---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/storefront/views/checkout_one_page.py

Symbols in `plugins/installed/storefront/views/checkout_one_page.py`.

- L42 `checkout_one_page(request)` (function) — Single-screen checkout — render or submit.
- L137 `_collect_address(request)` (function)
- L141 `_validate(addr: dict, *, no_shipping: bool)` (function)
- L160 `_shipping_input(addr: dict)` (function) — Map the storefront address form to GraphQL ``AddressInput`` fields.
- L180 `_submit_order(*, request, cart_id: str, addr: dict, rate_id: str, payment_method: str='')` (function)
- L214 `_redirect_to_confirmation(order_no: str)` (function)
- L234 `_render_form(request, *, addr: dict | None, rate_id: str, error: str, payment_method: str='')` (function)
- L258 `_payment_methods()` (function) — Enabled gateways for the checkout picker (fail-soft to []).

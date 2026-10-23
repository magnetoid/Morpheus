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

# plugins/installed/storefront/views/checkout.py

Symbols in `plugins/installed/storefront/views/checkout.py`.

- L23 `_load_cart_items(request)` (function) — The session cart with items + product/variant prefetched, or None.
- L36 `_item_ships(item)` (function) — Whether one cart item needs shipping (variant overrides product).
- L42 `_cart_requires_shipping(request)` (function) — Returns True if any cart item needs a shipping address. Digital /
- L60 `_cart_has_digital(request)` (function) — True if the cart contains at least one downloadable/digital item
- L74 `_withdrawal_waiver()` (function) — Merchant-configured digital withdrawal-waiver: ``{enabled, text}``.
- L91 `waiver_gate(request)` (function) — '' unless the cart needs the digital withdrawal-waiver and the POST
- L101 `record_waiver(order_no: str)` (function) — Stamp the accepted digital withdrawal-waiver onto the order (exact text
- L130 `_checkout_base_context(request)` (function) — Common context for every checkout step — cart summary + prefill.
- L175 `_cart_totals(request, cart: dict)` (function) — Real breakdown (discount/shipping/tax/total) for the summary rows.
- L199 `_stamp_checkout_email(request, email: str)` (function) — Persist the checkout-entered email onto the visitor's cart metadata.
- L235 `_available_shipping_rates(request, addr)` (function) — Rate options via the CHECKOUT_SHIPPING_RATES filter (shipping plugin).
- L258 `checkout(request)` (function) — Step 1: contact + shipping address.
- L318 `checkout_apply_gift_card(request)` (function) — POST /checkout/gift-card/apply/ — applies the gift card and bounces back.
- L339 `checkout_apply_coupon(request)` (function) — POST /checkout/coupon/apply/ — apply a promo code and bounce back.
- L371 `checkout_remove_coupon(request)` (function) — POST /checkout/coupon/remove/ — clear the applied promo code.
- L391 `checkout_remove_gift_card(request)` (function) — POST /checkout/gift-card/remove/ — clears the applied card.
- L411 `checkout_shipping(request)` (function) — Step 2: pick a shipping rate.
- L448 `checkout_review(request)` (function) — Step 3: final review + place order. POST creates the Order +
- L555 `checkout_payment(request)` (function) — Step 4: Stripe Payment Element.

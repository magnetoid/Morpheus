---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/storefront/views/checkout.py

Symbols in `plugins/installed/storefront/views/checkout.py`.

- L18 `_cart_requires_shipping(request)` (function) — Returns True if any cart item needs a shipping address. Digital /
- L66 `_checkout_base_context(request)` (function) — Common context for every checkout step — cart summary + prefill.
- L105 `_available_shipping_rates(request, addr)` (function) — Compute shipping rates; fall back to free standard if plugin off.
- L129 `checkout(request)` (function) — Step 1: contact + shipping address.
- L184 `checkout_apply_gift_card(request)` (function) — POST /checkout/gift-card/apply/ — applies the gift card and bounces back.
- L205 `checkout_remove_gift_card(request)` (function) — POST /checkout/gift-card/remove/ — clears the applied card.
- L225 `checkout_shipping(request)` (function) — Step 2: pick a shipping rate.
- L262 `checkout_review(request)` (function) — Step 3: final review + place order. POST creates the Order +
- L362 `checkout_payment(request)` (function) — Step 4: Stripe Payment Element.

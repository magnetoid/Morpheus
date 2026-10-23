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

# plugins/installed/payments/views.py

Symbols in `plugins/installed/payments/views.py`.

- L29 `stripe_webhook(request: HttpRequest)` (function) — Stripe POSTs raw JSON; we verify the signature inside PaymentService.
- L58 `_confirmation_redirect(order)` (function) — Redirect to the order-confirmation page, guest-safe via public_token.
- L69 `paypal_return(request: HttpRequest)` (function) — The shopper approved on PayPal — capture and mark the order paid.
- L113 `apple_pay_domain_association(request: HttpRequest)` (function) — Serve Stripe's Apple Pay domain-verification file.
- L142 `paypal_cancel(request: HttpRequest)` (function) — The shopper backed out on PayPal — return to checkout, cart intact.
- L154 `paypal_webhook(request: HttpRequest)` (function) — PayPal webhook receiver — backstop when the shopper never returns.

---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/payments/gateways/stripe_gateway.py

Symbols in `plugins/installed/payments/gateways/stripe_gateway.py`.

- L12 `StripeGateway` (class)
- L18 `create_payment_intent(self, *, order, **kwargs)` (method)
- L23 `refund(self, *, transaction, amount, **kwargs)` (method) — Issue a Stripe refund against the transaction's PaymentIntent.
- L64 `webhook_verify(self, *, body: bytes, signature: str)` (method)

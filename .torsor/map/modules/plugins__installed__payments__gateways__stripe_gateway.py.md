---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/payments/gateways/stripe_gateway.py

Symbols in `plugins/installed/payments/gateways/stripe_gateway.py`.

- L11 `StripeGateway` (class)
- L17 `create_payment_intent(self, *, order, **kwargs)` (method)
- L21 `refund(self, *, transaction, amount, **kwargs)` (method) — Issue a Stripe refund against the transaction's PaymentIntent.
- L59 `webhook_verify(self, *, body: bytes, signature: str)` (method)

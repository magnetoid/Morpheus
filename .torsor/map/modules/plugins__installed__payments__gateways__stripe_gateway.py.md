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

# plugins/installed/payments/gateways/stripe_gateway.py

Symbols in `plugins/installed/payments/gateways/stripe_gateway.py`.

- L12 `StripeGateway` (class)
- L18 `is_configured(self)` (method) — Both keys are needed: the secret one creates the intent, the
- L25 `create_payment_intent(self, *, order, **kwargs)` (method)
- L30 `refund(self, *, transaction, amount, **kwargs)` (method) — Issue a Stripe refund against the transaction's PaymentIntent.
- L74 `webhook_verify(self, *, body: bytes, signature: str)` (method)

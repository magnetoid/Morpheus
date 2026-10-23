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

# plugins/installed/payments/gateway.py

Symbols in `plugins/installed/payments/gateway.py`.

- L36 `PaymentGateway` (class) — Abstract payment provider. Plugins subclass + register an instance.
- L46 `is_configured(self)` (method) — Whether this gateway can take a payment right now.
- L56 `create_payment_intent(self, *, order, **kwargs)` (method) — Return {success: bool, client_secret?: str, transaction_id?: str, error?: str}.
- L59 `capture(self, *, transaction, **kwargs)` (method) — Capture a previously authorised payment (delayed-capture providers).
- L67 `refund(self, *, transaction, amount, **kwargs)` (method)
- L70 `webhook_verify(self, *, body: bytes, signature: str)` (method) — Return parsed webhook event dict, or None if signature invalid.
- L75 `GatewayRegistry` (class)
- L76 `__init__(self)` (method)
- L79 `register(self, gateway: PaymentGateway)` (method)
- L84 `unregister(self, slug: str)` (method)
- L87 `get(self, slug: str)` (method)
- L90 `all(self)` (method)
- L93 `enabled_gateways(self, *, user=None)` (method) — Registered gateways that are switched on, set up, and offered to ``user``.
- L111 `default(self, *, user=None)` (method) — Stripe when it can take payments, else the first working method.
- L126 `_configured(gateway: PaymentGateway)` (function)

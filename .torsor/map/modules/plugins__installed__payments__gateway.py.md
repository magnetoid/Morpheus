---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/payments/gateway.py

Symbols in `plugins/installed/payments/gateway.py`.

- L33 `PaymentGateway` (class) — Abstract payment provider. Plugins subclass + register an instance.
- L42 `create_payment_intent(self, *, order, **kwargs)` (method) — Return {success: bool, client_secret?: str, transaction_id?: str, error?: str}.
- L45 `capture(self, *, transaction, **kwargs)` (method) — Best-effort capture for delayed-capture providers.
- L49 `refund(self, *, transaction, amount, **kwargs)` (method)
- L52 `webhook_verify(self, *, body: bytes, signature: str)` (method) — Return parsed webhook event dict, or None if signature invalid.
- L57 `GatewayRegistry` (class)
- L58 `__init__(self)` (method)
- L61 `register(self, gateway: PaymentGateway)` (method)
- L66 `unregister(self, slug: str)` (method)
- L69 `get(self, slug: str)` (method)
- L72 `all(self)` (method)
- L75 `enabled_gateways(self)` (method) — Registered gateways whose Settings → Payments toggle is on.
- L88 `default(self)` (method)

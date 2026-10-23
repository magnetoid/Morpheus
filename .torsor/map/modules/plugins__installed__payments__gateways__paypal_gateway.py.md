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

# plugins/installed/payments/gateways/paypal_gateway.py

Symbols in `plugins/installed/payments/gateways/paypal_gateway.py`.

- L12 `PayPalGateway` (class)
- L18 `is_configured(self)` (method)
- L23 `create_payment_intent(self, *, order, **kwargs)` (method) — Create a PayPal order; the shopper approves at ``approval_url``.
- L49 `refund(self, *, transaction, amount, **kwargs)` (method) — Refund via the capture behind this PayPal order.
- L65 `webhook_verify(self, *, body: bytes, signature: str)` (method) — PayPal verification needs the full header set, not one signature —

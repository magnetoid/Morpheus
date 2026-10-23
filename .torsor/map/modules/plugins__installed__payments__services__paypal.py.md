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

# plugins/installed/payments/services/paypal.py

Symbols in `plugins/installed/payments/services/paypal.py`.

- L39 `get_config()` (function) — PayPal credentials/mode from the payments plugin config (fail-soft).
- L58 `base_url()` (function)
- L63 `is_configured()` (function)
- L68 `sync_gateway_row(*args, **kwargs)` (function) — Project the ``paypal_enabled`` panel toggle onto PaymentGatewayConfig.
- L88 `_access_token()` (function) — Client-credentials OAuth token, cached (~8h; PayPal issues 9h tokens).
- L109 `_headers()` (function)
- L116 `create_order(order)` (function) — Create a PayPal Order (intent=CAPTURE) for our Order.
- L171 `capture_order(paypal_order_id: str)` (function) — Capture an approved PayPal order. Returns {'success', 'capture_id'?, 'error'?}.
- L194 `get_capture_id(paypal_order_id: str)` (function) — Look up the capture id on a completed PayPal order (for refunds).
- L209 `refund_capture(capture_id: str, amount)` (function) — Refund a capture (partial when ``amount`` < captured total).
- L231 `verify_webhook(headers, body: bytes)` (function) — Verify a webhook delivery via PayPal's verify-webhook-signature API.
- L271 `mark_order_paid(paypal_order_id: str)` (function) — Mark the transaction/order for this PayPal order paid, exactly once.

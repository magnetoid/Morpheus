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

# plugins/installed/payments/app.py

Symbols in `plugins/installed/payments/app.py`.

- L12 `PaymentsPlugin` (class)
- L20 `ready(self)` (method)
- L78 `_on_own_config_saved(sender, instance, **kwargs)` (method)
- L84 `on_health_checks(self, value, **kwargs)` (method) — HEALTH_CHECKS: checkout offers at least one payment method that works.
- L105 `on_checkout_gateways(self, value, user=None, **kwargs)` (method) — CHECKOUT_GATEWAYS: enabled-gateway dicts for the checkout picker.
- L111 `on_order_placed(self, order, **kwargs)` (method) — Triggered when an order is placed.
- L119 `on_refund_requested(self, refund, **kwargs)` (method) — Drive the gateway-side refund when the dashboard records a Refund.
- L195 `get_config_schema(self)` (method)
- L236 `contribute_settings_panel(self)` (method)

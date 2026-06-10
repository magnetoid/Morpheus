---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/payments/plugin.py

Symbols in `plugins/installed/payments/plugin.py`.

- L11 `PaymentsPlugin` (class)
- L19 `ready(self)` (method)
- L42 `on_order_placed(self, order, **kwargs)` (method) — Triggered when an order is placed.
- L50 `on_refund_requested(self, refund, **kwargs)` (method) — Drive the gateway-side refund when the dashboard records a Refund.
- L111 `get_config_schema(self)` (method)
- L127 `contribute_settings_panel(self)` (method)

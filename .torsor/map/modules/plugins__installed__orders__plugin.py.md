---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/orders/plugin.py

Symbols in `plugins/installed/orders/plugin.py`.

- L10 `OrdersPlugin` (class)
- L18 `ready(self)` (method)
- L37 `get_config_schema(self)` (method)
- L57 `contribute_settings_panel(self)` (method)
- L65 `on_payment_captured(self, payment, **kwargs)` (method)
- L70 `on_order_placed(self, order, **kwargs)` (method) — Send the customer their order-confirmation email.
- L84 `on_account_summary(self, value, user=None, **kwargs)` (method) — Fold this customer's order count, open returns and store-credit
- L101 `on_activity_feed(self, value, limit=20, **kwargs)` (method) — Fold recent order events + return-request activity into the
- L134 `contribute_agent_tools(self)` (method)

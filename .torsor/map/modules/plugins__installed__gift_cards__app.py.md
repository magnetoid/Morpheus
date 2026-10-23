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

# plugins/installed/gift_cards/app.py

Symbols in `plugins/installed/gift_cards/app.py`.

- L11 `GiftCardsPlugin` (class)
- L21 `ready(self)` (method)
- L51 `on_order_paid(self, order=None, **kwargs)` (method) — Issue purchased gift cards on payment (idempotent; fail-soft —
- L70 `on_order_cancelled(self, order=None, **kwargs)` (method) — Re-credit any gift card spent on a cancelled order (idempotent,
- L89 `on_payment_refunded(self, refund=None, order=None, **kwargs)` (method) — Prorated re-credit of card tender on a refund/return (idempotent,
- L108 `on_cart_breakdown(self, value, cart=None, **kwargs)` (method) — Apply the cart's gift card as a tender against the FINAL total.
- L170 `get_config_schema(self)` (method)
- L189 `contribute_settings_panel(self)` (method)
- L199 `contribute_email_templates(self)` (method)
- L212 `on_account_summary(self, value, user=None, **kwargs)` (method) — Fold this customer's active gift cards into the account summary.
- L238 `contribute_dashboard_cards(self)` (method)
- L253 `contribute_dashboard_pages(self)` (method)
- L269 `contribute_agent_tools(self)` (method)

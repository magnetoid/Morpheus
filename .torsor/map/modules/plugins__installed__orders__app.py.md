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

# plugins/installed/orders/app.py

Symbols in `plugins/installed/orders/app.py`.

- L11 `OrdersPlugin` (class)
- L19 `ready(self)` (method)
- L87 `get_config_schema(self)` (method)
- L160 `contribute_settings_panel(self)` (method)
- L168 `on_health_checks(self, value, **kwargs)` (method) — HEALTH_CHECKS: a real product can be carted and priced (rolled back).
- L175 `on_restore_losses(self, value, since=None, **kwargs)` (method) — RESTORE_LOSSES: the orders placed since the backup was made.
- L184 `on_cart_breakdown_store_credit(self, value, cart=None, **kwargs)` (method) — Pay down the final total with the signed-in customer's store credit.
- L224 `on_order_cancelled_store_credit(self, order=None, **kwargs)` (method)
- L234 `on_payment_refunded_store_credit(self, refund=None, order=None, **kwargs)` (method)
- L244 `on_customer_email_verified(self, customer=None, email='', **kwargs)` (method) — CUSTOMER_EMAIL_VERIFIED: file the guest orders placed with this email
- L263 `on_customer_login(self, customer=None, request=None, **kwargs)` (method) — CUSTOMER_LOGIN: adopt/merge the anonymous-session cart onto the
- L279 `on_account_summary(self, value, user=None, **kwargs)` (method) — Fold this customer's order count, open returns and store-credit
- L296 `on_activity_feed(self, value, limit=20, **kwargs)` (method) — Fold recent order events + return-request activity into the
- L329 `contribute_agent_tools(self)` (method)

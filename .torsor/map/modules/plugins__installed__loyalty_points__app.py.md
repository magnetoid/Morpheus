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

# plugins/installed/loyalty_points/app.py

Symbols in `plugins/installed/loyalty_points/app.py`.

- L42 `LoyaltyPointsPlugin` (class)
- L54 `ready(self)` (method)
- L84 `on_account_summary(self, value, user=None, **kwargs)` (method) — Fold this customer's points balance into the account summary.
- L102 `on_activity_feed(self, value, limit=20, **kwargs)` (method) — Fold recent points awards into the dashboard home feed
- L127 `on_order_cancelled(self, order=None, **kwargs)` (method) — Reverse any loyalty redemption on a cancelled order (idempotent).
- L151 `on_payment_refunded(self, refund=None, order=None, **kwargs)` (method) — Prorated re-credit of spent points on a refund/return (idempotent,
- L172 `contribute_storefront_blocks(self)` (method)
- L192 `_requested_redeem(value, cart, customer)` (method) — Resolve the capped point spend for this cart, or 0 if none.
- L215 `on_cart_breakdown(self, value, cart=None, customer=None, **kwargs)` (method) — Turn ``cart.metadata['loyalty_points_redeem']`` into a discount.
- L249 `get_config_schema(self)` (method)
- L272 `contribute_dashboard_cards(self)` (method)
- L285 `contribute_settings_panel(self)` (method)
- L293 `contribute_agent_tools(self)` (method)

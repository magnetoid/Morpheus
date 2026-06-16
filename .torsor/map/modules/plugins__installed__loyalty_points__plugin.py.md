---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/loyalty_points/plugin.py

Symbols in `plugins/installed/loyalty_points/plugin.py`.

- L41 `LoyaltyPointsPlugin` (class)
- L53 `ready(self)` (method)
- L70 `on_account_summary(self, value, user=None, **kwargs)` (method) — Fold this customer's points balance into the account summary.
- L88 `on_activity_feed(self, value, limit=20, **kwargs)` (method) — Fold recent points awards into the dashboard home feed
- L113 `contribute_storefront_blocks(self)` (method)
- L125 `_requested_redeem(value, cart, customer)` (method) — Resolve the capped point spend for this cart, or 0 if none.
- L148 `on_cart_breakdown(self, value, cart=None, customer=None, **kwargs)` (method) — Turn ``cart.metadata['loyalty_points_redeem']`` into a discount.
- L182 `get_config_schema(self)` (method)
- L205 `contribute_settings_panel(self)` (method)

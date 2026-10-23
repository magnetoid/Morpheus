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

# plugins/installed/meta_commerce/app.py

Symbols in `plugins/installed/meta_commerce/app.py`.

- L19 `MetaCommercePlugin` (class)
- L34 `ready(self)` (method)
- L54 `_ad_spend(self, value, **_)` (method) — Contribute Meta's 30-day ad spend to the attribution ROAS pipeline.
- L69 `_channels_row(self, value, **_)` (method)
- L102 `_channels_metrics(self, value, **_)` (method)
- L125 `_bust_feed_cache(self, **_)` (method)
- L135 `_on_order_paid(self, order=None, **_)` (method)
- L142 `_on_add_to_cart(self, product=None, variant=None, quantity=1, request=None, **_)` (method)
- L152 `_on_begin_checkout(self, cart=None, request=None, **_)` (method)
- L159 `_capi(self, fn, label: str)` (method) — Run a CAPI send, swallowing every error — must never block the flow.
- L168 `contribute_storefront_blocks(self)` (method)
- L177 `contribute_dashboard_pages(self)` (method)
- L201 `contribute_settings_panel(self)` (method)
- L213 `contribute_agent_tools(self)` (method)
- L232 `get_config_schema(self)` (method)

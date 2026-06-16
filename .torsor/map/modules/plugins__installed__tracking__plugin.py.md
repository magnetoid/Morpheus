---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/tracking/plugin.py

Symbols in `plugins/installed/tracking/plugin.py`.

- L20 `TrackingPlugin` (class)
- L34 `ready(self)` (method)
- L55 `on_order_paid(self, order=None, **_)` (method)
- L64 `on_refund(self, order=None, amount=None, **_)` (method)
- L74 `on_add_to_cart(self, cart=None, item=None, product=None, variant=None, quantity=1, **_)` (method)
- L81 `on_remove_from_cart(self, cart=None, item=None, product=None, quantity=1, **_)` (method)
- L86 `on_begin_checkout(self, cart=None, **_)` (method)
- L91 `on_product_viewed(self, product=None, **_)` (method)
- L96 `on_signup(self, customer=None, **_)` (method)
- L99 `on_login(self, customer=None, **_)` (method)
- L102 `on_search(self, search_term='', **_)` (method)
- L105 `_fire(self, event_kind: str, **ctx)` (method) — Build the GA4 payload and POST via Measurement Protocol.
- L165 `contribute_dashboard_pages(self)` (method)
- L173 `contribute_settings_panel(self)` (method)
- L185 `get_config_schema(self)` (method)

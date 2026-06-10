---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/tracking/plugin.py

Symbols in `plugins/installed/tracking/plugin.py`.

- L20 `TrackingPlugin` (class)
- L34 `ready(self)` (method)
- L55 `on_order_paid(self, order=None, **_)` (method)
- L60 `on_refund(self, order=None, amount=None, **_)` (method)
- L66 `on_add_to_cart(self, cart=None, item=None, product=None, variant=None, quantity=1, **_)` (method)
- L71 `on_remove_from_cart(self, cart=None, item=None, product=None, quantity=1, **_)` (method)
- L76 `on_begin_checkout(self, cart=None, **_)` (method)
- L81 `on_product_viewed(self, product=None, **_)` (method)
- L86 `on_signup(self, customer=None, **_)` (method)
- L89 `on_login(self, customer=None, **_)` (method)
- L92 `on_search(self, search_term='', **_)` (method)
- L95 `_fire(self, event_kind: str, **ctx)` (method) — Build the GA4 payload and POST via Measurement Protocol.
- L151 `contribute_dashboard_pages(self)` (method)
- L159 `contribute_settings_panel(self)` (method)
- L171 `get_config_schema(self)` (method)

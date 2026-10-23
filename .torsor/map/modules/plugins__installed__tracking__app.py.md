---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/tracking/app.py

Symbols in `plugins/installed/tracking/app.py`.

- L21 `_is_crawler(request)` (function)
- L28 `_consent_overridden()` (function) — Settings → Tracking's debug-only "Ignore visitor consent" switch, which
- L39 `TrackingPlugin` (class)
- L53 `ready(self)` (method)
- L74 `on_order_paid(self, order=None, **_)` (method)
- L83 `on_refund(self, order=None, amount=None, **_)` (method)
- L93 `on_add_to_cart(self, cart=None, item=None, product=None, variant=None, quantity=1, request=None, **_)` (method)
- L108 `on_remove_from_cart(self, cart=None, item=None, product=None, quantity=1, request=None, **_)` (method)
- L122 `on_begin_checkout(self, cart=None, request=None, **_)` (method)
- L127 `on_product_viewed(self, product=None, request=None, **_)` (method)
- L136 `on_signup(self, customer=None, **_)` (method)
- L139 `on_login(self, customer=None, request=None, **_)` (method)
- L142 `on_search(self, search_term='', request=None, **_)` (method)
- L145 `_fire(self, event_kind: str, **ctx)` (method) — Build the GA4 payload and POST via Measurement Protocol.
- L220 `contribute_dashboard_pages(self)` (method)
- L239 `contribute_settings_panel(self)` (method)
- L251 `get_config_schema(self)` (method)

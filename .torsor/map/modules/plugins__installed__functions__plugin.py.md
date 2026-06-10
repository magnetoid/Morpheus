---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/functions/plugin.py

Symbols in `plugins/installed/functions/plugin.py`.

- L19 `_has_any_functions()` (function) — Cached `Function.objects.exists()` — 5-minute Redis TTL.
- L36 `FunctionsPlugin` (class)
- L46 `ready(self)` (method)
- L69 `on_calculate_price(self, value, product=None, customer=None, **kwargs)` (method) — Run all enabled `product.calculate_price` functions in priority order.
- L87 `on_calculate_cart_breakdown(self, value, cart=None, **kwargs)` (method) — Dispatch user functions targeting either the new breakdown

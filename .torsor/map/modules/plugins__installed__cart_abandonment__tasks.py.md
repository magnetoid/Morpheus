---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/cart_abandonment/tasks.py

Symbols in `plugins/installed/cart_abandonment/tasks.py`.

- L36 `_config()` (function) — Read plugin config with sensible defaults if the DB row is absent.
- L56 `_cart_email(cart)` (function) — Best-effort reach: customer's email, else the email the shopper typed
- L70 `scan_abandoned_carts(self)` (function) — Emit ``events.CART_ABANDONED`` once per newly-stale cart.
- L121 `_has_marketing_consent(cart)` (function) — True only when the cart owner's most recent consent log opts in to
- L146 `_drip_anchor(cart, now)` (function) — The stable timestamp the drip ages off.
- L166 `send_cart_recovery_drip(self)` (function) — Send each due, unsent recovery step for every still-open abandoned cart.
- L218 `_drip_cart(cart, now, cfg, send_templated_email)` (function) — Send every due+unsent step for one cart. Returns how many were sent.

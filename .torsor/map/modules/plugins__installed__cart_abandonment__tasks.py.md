---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/cart_abandonment/tasks.py

Symbols in `plugins/installed/cart_abandonment/tasks.py`.

- L25 `_config()` (function) — Read plugin config with sensible defaults if the DB row is absent.
- L42 `_cart_email(cart)` (function) — Best-effort reach: customer's email, or any session-bound shipping email.
- L53 `scan_abandoned_carts(self)` (function) — Emit ``events.CART_ABANDONED`` once per newly-stale cart.

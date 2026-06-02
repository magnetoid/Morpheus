---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/cart_abandonment/tasks.py

Symbols in `plugins/installed/cart_abandonment/tasks.py`.

- L24 `_config()` (function) — Read plugin config with sensible defaults if the DB row is absent.
- L40 `_cart_email(cart)` (function) — Best-effort reach: customer's email, or any session-bound shipping email.
- L51 `scan_abandoned_carts(self)` (function) — Emit ``events.CART_ABANDONED`` once per newly-stale cart.

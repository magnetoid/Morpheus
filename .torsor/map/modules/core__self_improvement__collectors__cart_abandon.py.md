---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# core/self_improvement/collectors/cart_abandon.py

Symbols in `core/self_improvement/collectors/cart_abandon.py`.

- L25 `on_cart_abandoned(*, cart: Any=None, email: str | None=None, **_: Any)` (function) — Hook handler — kwargs match `MorpheusEvents.CART_ABANDONED`.
- L58 `_safe_item_count(cart: Any)` (function) — Return cart.items.count() if available, else 0. Defensive — the

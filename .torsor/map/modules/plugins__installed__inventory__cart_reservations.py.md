---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/inventory/cart_reservations.py

Symbols in `plugins/installed/inventory/cart_reservations.py`.

- L52 `ReservationResult` (class) — Return shape for `reserve()` — `ok=False` blocks the cart-add.
- L61 `reserve(*, variant_id: str, cart_id: str, quantity: int)` (function) — Atomically increase this cart's hold on the variant.
- L117 `release(*, variant_id: str, cart_id: str, quantity: int | None=None)` (function) — Release some or all of this cart's hold on the variant.
- L148 `release_cart(cart_id: str)` (function) — Release every variant this cart has reserved.
- L178 `total_held(variant_id: str)` (function) — Sum of active cart holds for one variant — used by services that
- L253 `_redis()` (function) — Return a redis-py connection or None if unavailable.
- L261 `_reservations_enabled()` (function)
- L269 `_ttl_seconds()` (function)
- L274 `_self_key(variant_id: str, cart_id: str)` (function)
- L278 `_scan_pattern(variant_id: str)` (function)
- L282 `_current_held(variant_id: str, cart_id: str)` (function)
- L293 `_absolute_available(variant_id: str)` (function) — StockLevel.available_quantity sum minus existing DB reservations.
- L309 `_available(variant_id: str)` (function) — Reservable units remaining: absolute - sum(cart_holds across all carts).
- L319 `cache_alive()` (function)

---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/inventory/tasks.py

Symbols in `plugins/installed/inventory/tasks.py`.

- L14 `notify_back_in_stock(product_id: str)` (function) — Email all open BackInStockSubscription rows for this product.
- L53 `apply_price_schedules()` (function) — Apply any PriceSchedule rows whose effective_at has passed.
- L80 `reconcile_redis_stock()` (function) — Compare Redis stock counters to Postgres source of truth.
- L96 `find_abandoned_carts()` (function) — Mark carts > 1h old as abandoned and fire the cart.abandoned event.

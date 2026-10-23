---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/inventory/tasks.py

Symbols in `plugins/installed/inventory/tasks.py`.

- L24 `notify_back_in_stock(product_id: str)` (function) — Email all open BackInStockSubscription rows for this product.
- L69 `apply_price_schedules()` (function) — Apply any PriceSchedule rows whose effective_at has passed.
- L100 `reconcile_redis_stock()` (function) — Compare Redis stock counters to Postgres source of truth.
- L127 `run_stockout_forecast()` (function) — Daily: reconcile stockout alerts; alert staff for newly opened ones.

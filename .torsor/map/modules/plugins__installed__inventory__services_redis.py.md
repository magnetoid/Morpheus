---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/inventory/services_redis.py

Symbols in `plugins/installed/inventory/services_redis.py`.

- L44 `_conn()` (function) — Get a Redis client. Returns None when Redis is unconfigured.
- L54 `_key(variant_id: str)` (function)
- L58 `prime_from_postgres(variant_id: str)` (function) — Copy the current available_quantity from Postgres into Redis.
- L80 `reserve_atomic(variant_id: str, qty: int)` (function) — Atomically decrement ``stock:{variant_id}`` if remaining ≥ qty.
- L100 `release(variant_id: str, qty: int)` (function) — Inverse of reserve_atomic — used on cancel / payment failure.
- L113 `reconcile_stock(*, drift_threshold_pct: float=1.0)` (function) — Compare Redis counters to Postgres source of truth.

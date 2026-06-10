---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/inventory/tests/test_cart_reservations.py

Symbols in `plugins/installed/inventory/tests/test_cart_reservations.py`.

- L35 `_FakeRedis` (class) — In-memory stand-in for redis-py's subset we use.
- L42 `__init__(self)` (method)
- L45 `get(self, key)` (method)
- L48 `set(self, key, value, ex=None, keepttl=False)` (method)
- L51 `delete(self, *keys)` (method)
- L55 `scan(self, cursor=0, match='', count=200)` (method)
- L61 `eval(self, script, n_keys, *args)` (method) — Reproduce the Lua CHECK-AND-INCR in Python.
- L88 `_Reservations` (class) — Patch helper — installs the fake redis + a fake absolute_available.
- L91 `__init__(self, *, absolute=10, enabled=True)` (method)
- L97 `__enter__(self)` (method)
- L116 `__exit__(self, *exc)` (method)
- L121 `ReserveTests` (class)
- L122 `test_zero_quantity_returns_ok(self)` (method)
- L128 `test_first_reserve_returns_held_quantity(self)` (method)
- L134 `test_second_reserve_for_same_cart_accumulates(self)` (method)
- L143 `test_insufficient_stock_returns_not_ok(self)` (method)
- L150 `test_two_carts_within_capacity_both_ok(self)` (method)
- L157 `test_disabled_returns_ok_immediately(self)` (method)
- L163 `test_redis_unavailable_fails_open(self)` (method)
- L179 `ReleaseTests` (class)
- L180 `test_release_full_drops_key(self)` (method)
- L186 `test_release_partial_decrements(self)` (method)
- L192 `test_release_to_zero_drops_key(self)` (method)
- L199 `ReleaseCartTests` (class)
- L200 `test_drops_every_variant_for_one_cart(self)` (method)
- L213 `TotalHeldTests` (class)
- L214 `test_sums_across_carts_for_variant(self)` (method)
- L221 `test_other_variants_not_counted(self)` (method)
- L228 `ReservationResultShape` (class) — Sanity: the public dataclass shape is stable.
- L231 `test_default_fields_present(self)` (method)
- L236 `test_serialisable(self)` (method)

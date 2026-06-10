---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/loyalty_points/services.py

Symbols in `plugins/installed/loyalty_points/services.py`.

- L15 `get_balance(customer)` (function) — Sum of ``points`` for a customer's transactions. Zero for guests.
- L28 `award_points(customer, points: int, *, reason: str='earn_order', order_number: str='', note: str='')` (function) — Idempotent earn for a (customer, order_number) pair when reason='earn_order'.
- L53 `_on_order_paid(order=None, **_kwargs)` (function) — ORDER_PAID handler — award 1 point per currency unit, rounded down.
- L86 `register_handlers()` (function)

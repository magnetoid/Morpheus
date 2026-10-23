---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/consent.py

Symbols in `core/consent.py`.

- L20 `decision_for(request)` (function) — The visitor's decision (``request=None``: no visitor, nothing granted).
- L34 `stamp(request)` (function) — What an order records at checkout, read back by every later send.
- L39 `_permits(decision: dict, category: str)` (function)
- L43 `allowed(category: str, *, order=None, request=None)` (function) — May a server-side send of ``category`` data happen?
- L57 `marketing_customer_ids()` (function) — Customers whose latest decision allows marketing; ``None`` when the store

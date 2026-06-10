---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/orders/store_credit.py

Symbols in `plugins/installed/orders/store_credit.py`.

- L18 `_balance_row(customer)` (function)
- L27 `issue(customer, *, amount: Money, reference: str='', note: str='', created_by=None)` (function) — Add credit to the customer's account. Returns the new balance.
- L54 `redeem(customer, *, amount: Money, reference: str='', note: str='')` (function) — Deduct from the customer's balance. Raises ValueError if insufficient.
- L73 `balance(customer)` (function) — Read the current balance. Returns Money(0, USD) when no row exists yet.

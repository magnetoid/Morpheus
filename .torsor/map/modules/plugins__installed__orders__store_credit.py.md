---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/orders/store_credit.py

Symbols in `plugins/installed/orders/store_credit.py`.

- L19 `_balance_row(customer)` (function)
- L29 `issue(customer, *, amount: Money, reference: str='', note: str='', created_by=None)` (function) — Add credit to the customer's account. Returns the new balance.
- L60 `redeem(customer, *, amount: Money, reference: str='', note: str='')` (function) — Deduct from the customer's balance. Raises ValueError if insufficient.
- L83 `balance(customer)` (function) — Read the current balance. Returns Money(0, USD) when no row exists yet.

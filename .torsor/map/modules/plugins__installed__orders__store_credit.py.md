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

# plugins/installed/orders/store_credit.py

Symbols in `plugins/installed/orders/store_credit.py`.

- L19 `_balance_row(customer)` (function)
- L29 `issue(customer, *, amount: Money, reference: str='', note: str='', created_by=None)` (function) — Add credit to the customer's account. Returns the new balance.
- L60 `redeem(customer, *, amount: Money, reference: str='', note: str='')` (function) — Deduct from the customer's balance. Raises ValueError if insufficient.
- L83 `balance(customer)` (function) — Read the current balance. Returns Money(0, USD) when no row exists yet.
- L102 `available_for(customer, currency: str)` (function) — Spendable balance in ``currency`` (0 when none, or held in another currency).
- L112 `_used(order)` (function)
- L116 `_recredited(customer, reference: str)` (function)
- L127 `recredit_cancelled_order(order)` (function) — Return the store credit spent on a cancelled order — whatever refunds
- L151 `recredit_refund(order, refund)` (function) — Re-credit store credit in proportion to a refund: cash and credit are

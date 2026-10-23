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

# plugins/installed/loyalty_points/services_redeem.py

Symbols in `plugins/installed/loyalty_points/services_redeem.py`.

- L36 `redemption_rate()` (function) — Points needed to redeem 1.00 unit of store currency.
- L55 `max_redeem_fraction()` (function) — Cap on the fraction of an order's total that points may cover.
- L72 `points_to_amount(points: int, currency: str='USD')` (function) — Money value of ``points`` at the current redemption rate.
- L88 `amount_to_points(amount)` (function) — Points required to cover ``amount`` (Money or Decimal-like).
- L99 `max_redeemable(customer, order_total=None)` (function) — Largest point spend allowed for this customer right now.
- L141 `redeem_points(customer, points: int, *, order=None, reason: str='')` (function) — Spend ``points`` from ``customer``'s balance, return the discount Money.
- L185 `reverse_redemption(customer, points: int, *, order=None, reason: str='')` (function) — Refund a prior redemption — re-credit ``points`` to the customer.
- L211 `redeem_points_for_order(customer, points: int, *, order)` (function) — Idempotent order-time debit — spend ``points`` against ``order`` once.
- L231 `refund_redemption_for_order(order, refund)` (function) — Re-credit spent points in proportion to a refund — idempotent.
- L292 `reverse_redemption_for_order(order)` (function) — Re-credit whatever points were spent on ``order`` — idempotent.

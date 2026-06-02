---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/loyalty_points/services_redeem.py

Symbols in `plugins/installed/loyalty_points/services_redeem.py`.

- L34 `redemption_rate()` (function) — Points needed to redeem 1.00 unit of store currency.
- L54 `max_redeem_fraction()` (function) — Cap on the fraction of an order's total that points may cover.
- L74 `points_to_amount(points: int, currency: str='USD')` (function) — Money value of ``points`` at the current redemption rate.
- L90 `amount_to_points(amount)` (function) — Points required to cover ``amount`` (Money or Decimal-like).
- L101 `max_redeemable(customer, order_total=None)` (function) — Largest point spend allowed for this customer right now.
- L124 `redeem_points(customer, points: int, *, order=None, reason: str='')` (function) — Spend ``points`` from ``customer``'s balance, return the discount Money.
- L168 `reverse_redemption(customer, points: int, *, order=None, reason: str='')` (function) — Refund a prior redemption — re-credit ``points`` to the customer.

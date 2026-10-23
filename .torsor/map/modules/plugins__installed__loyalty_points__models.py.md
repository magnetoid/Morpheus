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

# plugins/installed/loyalty_points/models.py

Symbols in `plugins/installed/loyalty_points/models.py`.

- L17 `PointsTransaction` (class)
- L41 `__str__(self)` (method)
- L55 `LoyaltyTier` (class) — A status tier with a 12-month-revenue threshold + perks.
- L85 `__str__(self)` (method)
- L89 `CustomerTier` (class) — Current tier per customer — denormalised for fast PDP/cart lookups.
- L109 `__str__(self)` (method)
- L113 `CustomerRFM` (class) — Recency / Frequency / Monetary score per customer.
- L148 `__str__(self)` (method)

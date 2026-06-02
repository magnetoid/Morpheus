---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:53'
updated: '2026-06-02T18:07:53'
---

# plugins/installed/tax/models.py

Symbols in `plugins/installed/tax/models.py`.

- L22 `TaxCategory` (class) — Reduced-rate categories (e.g. books, food, children's clothing).
- L35 `__str__(self)` (method)
- L39 `TaxRegion` (class) — A taxable region — typically (country, region) pair.
- L55 `__str__(self)` (method)
- L59 `TaxRate` (class) — A tax rate scoped to (region × optional category).
- L82 `__str__(self)` (method)
- L86 `fraction(self)` (method)
- L90 `TaxConfiguration` (class) — Singleton-style configuration row.

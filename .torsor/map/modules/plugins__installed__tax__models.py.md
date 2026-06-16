---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/tax/models.py

Symbols in `plugins/installed/tax/models.py`.

- L23 `TaxCategory` (class) — Reduced-rate categories (e.g. books, food, children's clothing).
- L37 `__str__(self)` (method)
- L41 `TaxRegion` (class) — A taxable region — typically (country, region) pair.
- L58 `__str__(self)` (method)
- L62 `TaxRate` (class) — A tax rate scoped to (region × optional category).
- L90 `__str__(self)` (method)
- L94 `fraction(self)` (method)
- L98 `TaxConfiguration` (class) — Singleton-style configuration row.

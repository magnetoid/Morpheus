---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/tax/services.py

Symbols in `plugins/installed/tax/services.py`.

- L13 `_resolve_region(country: str, region: str)` (function) — Find the most specific matching region, falling back to country-only.
- L30 `_resolve_rate(region, category_code: str)` (function)
- L41 `compute_tax(*, line_items: Iterable[dict], country: str='', region: str='')` (function) — Compute tax for a list of line items.
- L108 `compute_tax_for_cart(cart, *, country: str='', region: str='')` (function) — Convenience wrapper: pull line items off a Cart.

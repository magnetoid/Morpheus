---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/tax/services.py

Symbols in `plugins/installed/tax/services.py`.

- L14 `_resolve_region(country: str, region: str)` (function) — Find the most specific matching region, falling back to country-only.
- L31 `_resolve_rate(region, category_code: str)` (function)
- L42 `compute_tax(*, line_items: Iterable[dict], country: str='', region: str='')` (function) — Compute tax for a list of line items.
- L115 `compute_tax_for_cart(cart, *, country: str='', region: str='')` (function) — Convenience wrapper: pull line items off a Cart.

---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/book_product/compat.py

Symbols in `plugins/installed/book_product/compat.py`.

- L18 `_product_ct()` (function)
- L26 `distinct_values(field: str)` (function) — Distinct non-empty values of a book `field` — model ∪ legacy metafields.
- L56 `distinct_active_values(field: str)` (function) — Distinct values of a book `field` that at least one ACTIVE product carries.
- L97 `product_ids_for(field: str, value: str)` (function) — Product ids whose book `field` == `value` (case-insensitive) — model ∪ metafields.
- L125 `book_attrs(product)` (function) — A product's book attributes as a flat ``{key: value}`` dict with bare
- L195 `set_book_attrs(product, raw: dict)` (function) — Upsert a BookProduct from a raw ``book.*``-shaped dict (author, publisher,
- L243 `resolve_slug(field: str, slug: str)` (function) — Reverse a slug back to the stored value for `field` (e.g. /author/<slug>/).

---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/book_product/compat.py

Symbols in `plugins/installed/book_product/compat.py`.

- L18 `_product_ct()` (function)
- L26 `distinct_values(field: str)` (function) — Distinct non-empty values of a book `field` — model ∪ legacy metafields.
- L56 `product_ids_for(field: str, value: str)` (function) — Product ids whose book `field` == `value` (case-insensitive) — model ∪ metafields.
- L84 `book_attrs(product)` (function) — A product's book attributes as a flat ``{key: value}`` dict with bare
- L154 `set_book_attrs(product, raw: dict)` (function) — Upsert a BookProduct from a raw ``book.*``-shaped dict (author, publisher,
- L202 `resolve_slug(field: str, slug: str)` (function) — Reverse a slug back to the stored value for `field` (e.g. /author/<slug>/).

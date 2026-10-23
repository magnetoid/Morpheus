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

# plugins/installed/book_product/listing_facets.py

Symbols in `plugins/installed/book_product/listing_facets.py`.

- L34 `selections(params)` (function) — Each facet's chosen values from repeated query keys; blanks and repeats dropped.
- L47 `_variant_products(**kw)` (function)
- L53 `_format_q(value: str)` (function)
- L70 `_length_q(value: str)` (function)
- L83 `_facet_q(key: str, values: list[str])` (function) — The OR of a facet's values, or None when no value means anything.
- L104 `apply(qs, chosen: dict, *, skip: str | None=None)` (function) — Narrow `qs` by every chosen facet except `skip`.
- L116 `_scope(base_qs, chosen, key)` (function)
- L123 `_options(rows, selected: list[str], *, fold=False)` (function) — rows: [(value, label, count)] → option dicts; zero counts dropped unless selected;
- L139 `_taxonomy_rows(model, scope, *, min_books=1)` (function)
- L149 `_facet(key, label, options, *, searchable=False)` (function)
- L159 `describe(base_qs, chosen: dict)` (function) — Every facet with its options and counts; a facet with no options is left out.
- L209 `answer(value: dict, params)` (function) — LISTING_FACETS: narrow the listing by the book facets and describe them.

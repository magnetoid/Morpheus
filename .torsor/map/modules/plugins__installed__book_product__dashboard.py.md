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

# plugins/installed/book_product/dashboard.py

Symbols in `plugins/installed/book_product/dashboard.py`.

- L33 `book_widget_context(product)` (function) — Context for the 'Book details' card on the product-edit page.
- L61 `_book_identifiers(product)` (function) — Current ISBN / OCLC / Open Library values for the edit form. ISBN-13
- L82 `_save_book_identifiers(product, post)` (function) — Persist ISBN-13 / OCLC / Open Library work id from the book card.
- L100 `_facets(book, slugify)` (function) — The category-style facet pages this book appears on (label, value, url).
- L139 `_apply_translation_of(book, raw)` (function) — Link a language edition to the ORIGINAL work by product slug.
- L161 `save_book_fields(product, post, files=None)` (function) — Upsert the BookProduct from the product form's book.* inputs.
- L209 `_parse_date(raw: str)` (function)

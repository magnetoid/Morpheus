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

# plugins/installed/book_product/facets.py

Symbols in `plugins/installed/book_product/facets.py`.

- L17 `value_facet_url(prefix: str, value: str | None)` (function) — ``/<prefix>/<value>/`` when the facet route can serve ``value``, else ``''``.
- L65 `canonical_language(value: str | None)` (function) — The code a stored language value means: `English` → `en`, `en-US` → `en`.
- L81 `language_spellings(code: str)` (function) — Every stored spelling that means `code` — the code and its English name.

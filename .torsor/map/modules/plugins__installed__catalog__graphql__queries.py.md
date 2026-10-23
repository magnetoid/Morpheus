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

# plugins/installed/catalog/graphql/queries.py

Symbols in `plugins/installed/catalog/graphql/queries.py`.

- L30 `_clamp_first(first: int)` (function)
- L34 `_apply_fts(qs, term: str)` (function) — Postgres full-text search with relevance, LIKE fallback elsewhere.
- L68 `_scope_to_channel(qs, info)` (function)
- L76 `CatalogQueryExtension` (class)
- L78 `product(self, info: strawberry.Info, slug: str)` (method)
- L91 `products(self, info: strawberry.Info, first: int=50, featured: bool | None=None, search: str | None=None, category: str | None=None)` (method)
- L123 `collections(self, info: strawberry.Info, first: int=50, featured: bool | None=None)` (method)
- L136 `categories(self, info: strawberry.Info, first: int=50, top_level: bool | None=None)` (method)

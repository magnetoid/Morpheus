---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/catalog/graphql/queries.py

Symbols in `plugins/installed/catalog/graphql/queries.py`.

- L29 `_clamp_first(first: int)` (function)
- L33 `_apply_fts(qs, term: str)` (function) — Postgres full-text search with relevance, LIKE fallback elsewhere.
- L67 `_scope_to_channel(qs, info)` (function)
- L75 `CatalogQueryExtension` (class)
- L77 `product(self, info: strawberry.Info, slug: str)` (method)
- L87 `products(self, info: strawberry.Info, first: int=50, featured: bool | None=None, search: str | None=None, category: str | None=None)` (method)
- L117 `collections(self, info: strawberry.Info, first: int=50, featured: bool | None=None)` (method)
- L130 `categories(self, info: strawberry.Info, first: int=50, top_level: bool | None=None)` (method)

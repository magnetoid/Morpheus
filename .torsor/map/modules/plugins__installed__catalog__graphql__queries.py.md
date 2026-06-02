---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/catalog/graphql/queries.py

Symbols in `plugins/installed/catalog/graphql/queries.py`.

- L31 `_clamp_first(first: int)` (function)
- L35 `_apply_fts(qs, term: str)` (function) — Postgres full-text search with relevance, LIKE fallback elsewhere.
- L69 `_scope_to_channel(qs, info)` (function)
- L77 `CatalogQueryExtension` (class)
- L79 `product(self, info: strawberry.Info, slug: str)` (method)
- L89 `products(self, info: strawberry.Info, first: int=50, featured: Optional[bool]=None, search: Optional[str]=None, category: Optional[str]=None)` (method)
- L119 `collections(self, info: strawberry.Info, first: int=50, featured: Optional[bool]=None)` (method)
- L132 `categories(self, info: strawberry.Info, first: int=50, top_level: Optional[bool]=None)` (method)

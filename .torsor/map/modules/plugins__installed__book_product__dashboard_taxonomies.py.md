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

# plugins/installed/book_product/dashboard_taxonomies.py

Symbols in `plugins/installed/book_product/dashboard_taxonomies.py`.

- L38 `_curated_model(kind)` (function)
- L44 `_curated_groups()` (function)
- L118 `taxonomies_list(request: HttpRequest)` (function)
- L165 `taxonomy_edit(request: HttpRequest, taxonomy: str, slug: str)` (function)
- L214 `taxonomy_root_edit(request: HttpRequest, taxonomy: str)` (function) — Edit the landing page for a whole taxonomy kind (e.g. /authors/,
- L261 `_curated_breadcrumb(label, extra)` (function)
- L272 `curated_add(request: HttpRequest, kind: str)` (function) — Create a curated Genre/Topic (curated taxonomies need a create path that
- L292 `curated_edit(request: HttpRequest, kind: str, slug: str)` (function) — Edit a Genre/Topic landing page — name, intro, SEO, image. Same UX as a
- L336 `curated_backfill(request: HttpRequest, kind: str)` (function) — Queue the bulk copy backfill for a curated kind (Genres/Topics).
- L389 `curated_delete(request: HttpRequest, kind: str, slug: str)` (function)
- L399 `taxonomy_generate(request: HttpRequest, taxonomy: str, slug: str='')` (function) — AI-generate the intro + SEO for a taxonomy page — a term when `slug` is

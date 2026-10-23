---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/storefront/views/home.py

Symbols in `plugins/installed/storefront/views/home.py`.

- L11 `_serialize_product(p)` (function) — ORM Product → the GraphQL-shaped dict the home template renders.
- L53 `_has_real_cover(product)` (function) — True when the book's cover is artwork, not a drawn stand-in.
- L73 `_hero_with_covers(picks: list, pool: list, limit: int=4)` (function) — Hero picks that have real artwork, topped up from the featured pool.
- L93 `_surface_products(request, surface: str, *, value=None, limit: int=8)` (function) — Fire the merchandising-takeover hook for one placeholder (fail-soft).
- L109 `home(request)` (function)

---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/demo_data/services.py

Symbols in `plugins/installed/demo_data/services.py`.

- L23 `SeedSummary` (class)
- L26 `inc(self, key: str, n: int=1)` (method)
- L30 `seed_all(*, currency: str='USD', wipe: bool=False)` (function) — Seed the demo dataset. Re-runnable; will not duplicate rows.
- L53 `_seed_taxonomy(summary: SeedSummary)` (function) — Seed the single ``Books`` category + one Genre per ``seeds.CATEGORIES``
- L83 `_seed_collections(summary: SeedSummary)` (function)
- L103 `_seed_vendors(summary: SeedSummary)` (function)
- L122 `_seed_books(summary: SeedSummary, books_cat: Any, genre_by_slug: dict[str, Any], ven_by_slug: dict[str, Any], col_by_slug: dict[str, Any], currency: str)` (function)
- L162 `_assign_genre(product, genre)` (function) — Tag a seeded book with its genre (model-first; fail-soft if book_product
- L176 `_seed_book_metafields(product, slug: str)` (function) — Write book.* metafields for the seeded book — fails closed so the
- L199 `_seed_book_cover(product, slug: str)` (function) — Download the Project Gutenberg cover and attach as a ProductImage.
- L228 `_seed_customers(summary: SeedSummary)` (function)
- L246 `_seed_orders(summary: SeedSummary, currency: str)` (function) — Create a couple of completed orders for nicer dashboard numbers.
- L295 `_wipe_demo(summary: SeedSummary)` (function) — Remove rows seeded by this loader. Identifies them by slug/email.
- L406 `_detect_topic()` (function) — Best-effort: read the active theme's `demo_topic` attribute.
- L426 `seed_random_products(*, count: int=30, topic: str='', currency: str='USD', wipe_random: bool=False)` (function) — Generate N random products themed for the active storefront.

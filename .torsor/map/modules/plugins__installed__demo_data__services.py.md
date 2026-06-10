---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/demo_data/services.py

Symbols in `plugins/installed/demo_data/services.py`.

- L23 `SeedSummary` (class)
- L26 `inc(self, key: str, n: int=1)` (method)
- L30 `seed_all(*, currency: str='USD', wipe: bool=False)` (function) — Seed the demo dataset. Re-runnable; will not duplicate rows.
- L53 `_seed_categories(summary: SeedSummary)` (function)
- L68 `_seed_collections(summary: SeedSummary)` (function)
- L88 `_seed_vendors(summary: SeedSummary)` (function)
- L107 `_seed_books(summary: SeedSummary, cat_by_slug: dict[str, Any], ven_by_slug: dict[str, Any], col_by_slug: dict[str, Any], currency: str)` (function)
- L144 `_seed_book_metafields(product, slug: str)` (function) — Write book.* metafields for the seeded book — fails closed so the
- L167 `_seed_book_cover(product, slug: str)` (function) — Download the Project Gutenberg cover and attach as a ProductImage.
- L196 `_seed_customers(summary: SeedSummary)` (function)
- L214 `_seed_orders(summary: SeedSummary, currency: str)` (function) — Create a couple of completed orders for nicer dashboard numbers.
- L263 `_wipe_demo(summary: SeedSummary)` (function) — Remove rows seeded by this loader. Identifies them by slug/email.
- L367 `_detect_topic()` (function) — Best-effort: read the active theme's `demo_topic` attribute.
- L387 `seed_random_products(*, count: int=30, topic: str='', currency: str='USD', wipe_random: bool=False)` (function) — Generate N random products themed for the active storefront.

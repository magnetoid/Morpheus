---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/demo_data/services.py

Symbols in `plugins/installed/demo_data/services.py`.

- L19 `SeedSummary` (class)
- L22 `inc(self, key: str, n: int=1)` (method)
- L26 `seed_all(*, currency: str='USD', wipe: bool=False)` (function) — Seed the demo dataset. Re-runnable; will not duplicate rows.
- L49 `_seed_categories(summary: SeedSummary)` (function)
- L64 `_seed_collections(summary: SeedSummary)` (function)
- L84 `_seed_vendors(summary: SeedSummary)` (function)
- L103 `_seed_books(summary: SeedSummary, cat_by_slug: dict[str, Any], ven_by_slug: dict[str, Any], col_by_slug: dict[str, Any], currency: str)` (function)
- L140 `_seed_book_metafields(product, slug: str)` (function) — Write book.* metafields for the seeded book — fails closed so the
- L154 `_seed_book_cover(product, slug: str)` (function) — Download the Project Gutenberg cover and attach as a ProductImage.
- L182 `_seed_customers(summary: SeedSummary)` (function)
- L200 `_seed_orders(summary: SeedSummary, currency: str)` (function) — Create a couple of completed orders for nicer dashboard numbers.
- L241 `_wipe_demo(summary: SeedSummary)` (function) — Remove rows seeded by this loader. Identifies them by slug/email.
- L306 `_detect_topic()` (function) — Best-effort: read the active theme's `demo_topic` attribute.
- L326 `seed_random_products(*, count: int=30, topic: str='', currency: str='USD', wipe_random: bool=False)` (function) — Generate N random products themed for the active storefront.

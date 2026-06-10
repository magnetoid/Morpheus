---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/advanced_ecommerce/templatetags/advanced_ecommerce.py

Symbols in `plugins/installed/advanced_ecommerce/templatetags/advanced_ecommerce.py`.

- L15 `recently_viewed_product(slug: str)` (function) — Return a Product by slug or None. Used in the recently-viewed rail.
- L28 `free_shipping_target()` (function) — Returns (target_amount, currency) tuple from plugin config.
- L45 `low_stock_threshold()` (function)
- L56 `featured_collection_rails(exclude_slug: str='', per_rail: int=8, max_rails: int=3)` (function) — Featured collections (with products) for the homepage rails.
- L101 `product_total_stock(product)` (function) — Sum of available stock across all variants of a product.

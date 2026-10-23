---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# plugins/feed_mapping.py

Symbols in `plugins/feed_mapping.py`.

- L33 `_abs(url: str)` (function)
- L59 `_availability_from_inventory(product)` (function) — The inventory app's answer, or '' when it is not installed / cannot tell.
- L84 `availability_to_schema(product)` (function) — A product (model or GraphQL dict) → a schema.org availability URL.
- L115 `FeedMapper` (class) — Product → flat feed-item dict, parameterized by channel.
- L122 `__init__(self, namespace: str, *, logger_name: str='')` (method)
- L127 `channel_fields(self, item: dict, *, product, over, book, gtin, mpn, settings)` (method) — Channel-specific attributes, added after identifiers and before
- L135 `_overrides(self, product)` (method)
- L144 `_identifiers(self, product)` (method)
- L161 `_availability_for(self, filter_kwargs: dict, *, include_oos: bool)` (method)
- L180 `_money(m)` (method) — Money → '9.00 USD' (the channels' shared price format).
- L190 `_primary_image_link(product)` (method)
- L197 `_price_pair(self, product)` (method) — (price, sale_price) strings; on-sale shows compare_at as regular.
- L205 `map_product(self, product, settings)` (method) — Flat ``{attr: value}`` feed item, or None when the product is
- L265 `expand_variants(self, product, base_item: dict, settings)` (method) — Variable product with ≥2 active variants → one item per variant

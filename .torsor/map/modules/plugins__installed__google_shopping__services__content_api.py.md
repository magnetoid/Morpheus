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

# plugins/installed/google_shopping/services/content_api.py

Symbols in `plugins/installed/google_shopping/services/content_api.py`.

- L27 `_content_product(item: dict, settings)` (function) — Feed-attr dict (from map_product) → Content API product resource.
- L61 `push_products(*, dry_run: bool=False)` (function) — Upsert every eligible product to Merchant Center. Returns a stats dict.
- L97 `product_statuses(*, max_pages: int=4)` (function) — Pull Merchant Center product statuses → disapproval/issue diagnostics.
- L157 `_post_batches(mid: str, entries: list[dict])` (function)
- L184 `_log(sent: int, errors: list[str])` (function)

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

# plugins/installed/personalisation/services.py

Symbols in `plugins/installed/personalisation/services.py`.

- L29 `recompute_copurchases(*, window_days: int=DEFAULT_WINDOW_DAYS, top_k: int=DEFAULT_TOP_K)` (function) — Rebuild the CoPurchaseScore table.
- L119 `_as_product(obj)` (function) — Normalize a Product model OR a GraphQL dict to a Product instance (or None).
- L142 `related_to(product, *, k: int=4)` (function) — Return up to k Product instances most-bought-with `product`.
- L168 `_ordered_pairs(products: set[str])` (function) — Yield each unordered pair exactly once as a sorted tuple.
- L190 `_recent_product_ids(request)` (function) — Product ids the visitor recently viewed (newest-first, de-duped), read
- L230 `_embeddings_for(ids)` (function)
- L244 `_centroid(vectors: list)` (function)
- L260 `_copurchase_affinity(anchor_ids)` (function)
- L273 `rank_for_visitor(request, products, *, surface: str='')` (function) — Reorder `products` by per-visitor purchase propensity.
- L322 `pairs_with(product, request=None, k: int=10)` (function) — 'Pairs with this' recommendations for the PDP — a dynamic blend:

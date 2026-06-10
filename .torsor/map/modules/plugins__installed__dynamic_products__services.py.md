---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/dynamic_products/services.py

Symbols in `plugins/installed/dynamic_products/services.py`.

- L45 `recommend(block, *, request=None, customer=None, context_product=None)` (function) — Return up to ``block.limit`` products for ``block``.
- L82 `_manual(block, *, limit, **_)` (function) — Filtered catalog slice: category / tags / metafields, newest first.
- L91 `_recently_viewed(block, *, request, customer, limit, **_)` (function) — Products this visitor recently looked at — session first, then durable.
- L96 `_related(block, *, context_product, limit, **_)` (function) — Same primary category / shared tags / shared metafields as the PDP product.
- L103 `_bought_together(block, *, context_product, customer, limit, **_)` (function) — Co-purchase, reusing the personalisation plugin's precomputed scores.
- L117 `_for_you(block, *, request, customer, context_product, limit, **_)` (function) — The personalized blend — the "best next purchase for this user" path.
- L187 `_recent_view_ids(request, customer, *, limit)` (function) — Ordered recently-viewed product ids. Session slugs first (freshest,
- L223 `_related_ids(product, *, limit)` (function) — Same primary category → shared tags → shared metafields.
- L259 `_copurchase_ids(product, *, limit)` (function) — Reuse the personalisation plugin's precomputed co-purchase scores.
- L271 `_live_copurchase_ids(anchor_ids, *, limit)` (function) — Live co-occurrence scan: products that appeared in paid orders
- L302 `_affinity_categories(purchased_ids, viewed_ids)` (function) — Top categories by combined purchase + view weight.
- L318 `_purchased_ids(customer)` (function) — Product ids the customer has already bought (any non-cancelled order).
- L331 `_cart_ids(request, customer)` (function) — Product ids currently in the visitor's cart (session or customer).
- L356 `_base_active_qs()` (function)
- L362 `_apply_filters(qs, block)` (function) — Apply a block's declarative category / tag / metafield filters.
- L382 `_metafield_product_ids(key, value)` (function) — Product ids carrying ``key`` (and ``value`` if given). Returns None
- L399 `_metafield_neighbours_qs(product)` (function) — Other active products sharing any of ``product``'s metafield (key,value).
- L430 `_materialize(ids, limit)` (function) — De-dupe (preserving order), fetch active products, slice to limit.

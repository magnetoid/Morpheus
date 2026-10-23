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

# plugins/installed/dynamics/services.py

Symbols in `plugins/installed/dynamics/services.py`.

- L45 `recommend(block, *, request=None, customer=None, context_product=None)` (function) — Return up to ``block.limit`` products for ``block``.
- L85 `_apply_block_options(ids, block, *, request=None, customer=None)` (function) — Post-strategy block options that can't live in the DB filter: drop the
- L120 `_manual(block, *, limit, **_)` (function) — Filtered catalog slice: category / tags / metafields, newest first, and
- L137 `_recently_viewed(block, *, request, customer, limit, **_)` (function) — Products this visitor recently looked at — session first, then durable.
- L142 `_related(block, *, context_product, limit, **_)` (function) — Same primary category / shared tags / shared metafields as the PDP product.
- L149 `_bought_together(block, *, context_product, customer, limit, **_)` (function) — Co-purchase, reusing the personalisation plugin's precomputed scores.
- L163 `_for_you(block, *, request, customer, context_product, limit, **_)` (function) — The personalized blend — the "best next purchase for this user" path.
- L228 `_probability_grid(block, *, request, customer, limit, **_)` (function) — Returns products sorted by real-time purchase probability score for dynamic grid layout.
- L261 `_autopilot(block, *, request, customer, limit, **_)` (function) — Self-optimizing per-visitor strategy: take the propensity-ranked candidate
- L299 `smart_scored(block, *, request=None)` (function) — Ordered ``[(product_id, score, components)]`` for the smart blend.
- L335 `_session_category_ids(request)` (function) — Category ids of the products viewed in THIS session (consent-light,
- L350 `_smart(block, *, request, customer, limit, **_)` (function) — The explainable blend + exploration floor + diversity cap.
- L382 `exploration_picks(block, *, exclude: set, count: int)` (function) — Least-exposed products for the exploration floor: fewest bandit trials
- L403 `explain_block(block, *, request=None, customer=None)` (function) — Dashboard preview: the block's picks with per-product score breakdown.
- L447 `reason_label(block)` (function) — A short shopper-facing 'why' label for a block's products (B3 show_reason).
- L463 `_trending(block, *, limit, **_)` (function) — Highest product-view velocity over the last 7 days — what's hot now.
- L477 `_new_arrivals(block, *, limit, **_)` (function) — Newest active products first (respecting the block's filters).
- L483 `_best_sellers(block, *, limit, **_)` (function) — Most units sold in paid orders over the last 90 days, and nothing before
- L497 `_on_sale(block, *, limit, **_)` (function) — Active products whose compare-at price beats the current price.
- L508 `_similar_price(block, *, context_product, limit, **_)` (function) — Product-page strategy: other products within ±30% of this one's price,
- L529 `_propensity_map(ids)` (function) — product_id -> Phase-1 purchase_probability, for the reranker blend.
- L540 `_category_map(ids)` (function) — product_id -> category_id, for the reranker's per-category diversity cap.
- L545 `calculate_grid_probabilities(*, sales_window_days: int=60, view_window_days: int=30, trend_window_days: int=14)` (function) — Recompute ``DynamicGridItem.purchase_probability`` for every active product
- L636 `_persist_scores(products, scores, now)` (function) — Write purchase_probability + denormalized display fields to DynamicGridItem
- L675 `_units_sold(since, until=None)` (function) — product_id -> units sold in PAID orders in the window (canonical statuses).
- L688 `_view_counts(since, until=None)` (function) — product_slug -> product_view events in the window. Analytics is optional.
- L704 `_ratings(pids)` (function) — product_id -> avg rating normalized to [0,1]. Reviews are optional.
- L723 `_inventory_factors(pids, tracking_pids)` (function) — product_id -> stock factor in [0,1]. Only products that TRACK inventory and
- L750 `_minmax(raw: dict, pids: list)` (function) — Min-max normalize component values across the catalog to [0,1]. A flat
- L766 `_recent_view_ids(request, customer, *, limit)` (function) — Ordered recently-viewed product ids. Session slugs first (freshest,
- L800 `_related_ids(product, *, limit)` (function) — Same primary category → shared tags → shared metafields.
- L836 `_copurchase_ids(product, *, limit)` (function) — Reuse the personalisation plugin's precomputed co-purchase scores.
- L848 `_live_copurchase_ids(anchor_ids, *, limit)` (function) — Live co-occurrence scan: products that appeared in paid orders
- L879 `_affinity_categories(purchased_ids, viewed_ids)` (function) — Top categories by combined purchase + view weight.
- L895 `_purchased_ids(customer)` (function) — Product ids the customer has already bought (any non-cancelled order).
- L908 `_cart_ids(request, customer)` (function) — Product ids currently in the visitor's cart (session or customer).
- L933 `_base_active_qs()` (function)
- L939 `_apply_filters(qs, block)` (function) — Apply a block's declarative category / tag / metafield filters. A category
- L975 `_in_stock_ids()` (function) — Product ids with > 0 available stock (summed over variants). Returns None
- L992 `_metafield_product_ids(key, value)` (function) — Product ids carrying ``key`` (and ``value`` if given). Returns None
- L1009 `_metafield_neighbours_qs(product)` (function) — Other active products sharing any of ``product``'s metafield (key,value).
- L1040 `_materialize(ids, limit)` (function) — De-dupe (preserving order), fetch active products, slice to limit.
- L1066 `see_all_url(block)` (function) — The shop page that lists everything a block picks from, or '' when none can.
- L1093 `rebuild_bandit_posteriors(*, window_days: int=30)` (function) — Rebuild every BanditArm posterior from real product-view engagement,
- L1141 `_upsert_arms(agg)` (function) — Two-pass bulk upsert of BanditArm rows from an

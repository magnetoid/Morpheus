# Per-visitor merchandising — 2026-06

**Goal (user):** storefront books stay in their **same placeholders**, but each
slot is filled with the titles *this visitor* is most likely to buy —
"dynamically showing me books with the biggest chance for me to buy", and
"show me another book very similar to what I watched before". Per
taxonomy / collection / category / list.

## Approach: a reorder filter over the substrate that already exists

No new tracking infra — Morpheus already has all the parts:

- **Behavior**: `analytics.AnalyticsEvent(kind='product_view', product_slug,
  session)`, visitor identified by the `morph_aid` cookie
  (`AnalyticsSession.cookie_id`). Written by the analytics JS beacon.
- **Similarity**: `ai_assistant.ProductEmbedding(product, vector)` +
  `core.embeddings.cosine_similarity`.
- **Buy-affinity**: `personalisation.CoPurchaseScore(anchor, related, score)`.
- **Consent**: `personalisation` `_has_consent(request)` (functional cookie).

### The seam: `PRODUCT_LIST_REORDER` (new core filter hook)

`core/hooks.py`: `PRODUCT_LIST_REORDER = 'product.list.reorder'  # filter`
— value=list[Product], kwargs `request`, `surface`. Storefront surfaces fire
it; the `personalisation` plugin subscribes. Disable the plugin → no
subscriber → every list renders in its original order (disable-safe).

### The scorer: `personalisation.services.rank_for_visitor(request, products, surface)`

1. No-op guards (return original order): <2 items, non-Product list (GraphQL
   dicts), no functional consent, no view history, no usable signal.
2. `recent` = visitor's recently-viewed product ids (from AnalyticsEvent).
3. `interest` = centroid of recent products' embeddings.
4. `score(p) = W_EMBED·cosine(interest, emb[p]) + W_COPURCHASE·copurchase[p]
   − penalty if already viewed` (favour discovery). Stable sort, desc.
5. Fail-soft everywhere (analytics / ai_assistant may be disabled → empty
   signal → original order).

### Wired surfaces (fire the filter)

- `storefront author_detail` bibliography — surface='author' (the user's
  literal example).
- `storefront _related_products` (PDP "you might also like") — surface='related'.
- `book_product _render` facets (publisher / imprint / format / language) —
  surface='facet'. **Series opts out** (keeps `series_position` reading order).

### Deliberately deferred

- **PLP `product_list`** — paginated; reordering must happen pre-pagination
  (bigger change). Not wired yet.
- **Home page rails** — built from GraphQL dicts, not Product instances; the
  scorer passes dict lists through unchanged.
- **Caching** — scorer runs ~3 indexed queries per personalised list; add a
  per-session cache if it shows up in profiling.

## Tests

`personalisation/tests/test_personalised_merch.py`: reorders similar-first;
no-consent / no-history / single-item / non-Product → original order; the
`PRODUCT_LIST_REORDER` filter reorders end-to-end when the plugin is active.

## Privacy

Strictly consent-gated (functional). No new PII; reads the existing analytics
event log + embeddings. Anonymous visitors with no history get today's order.

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

# core/tests/test_cache_invalidation.py

Symbols in `core/tests/test_cache_invalidation.py`.

- L24 `CacheKeyContractTests` (class)
- L25 `_graphql_key(self)` (method) — Build a key exactly as api/middleware.py (the REAL writer) does.
- L32 `test_the_invalidator_matches_a_real_graphql_cache_key(self)` (method)
- L41 `test_the_key_format_has_not_moved(self)` (method) — Guard the REAL writer. The cache is written by the GraphQL cache
- L61 `test_locmem_fallback_clears_everything(self)` (method) — Dev/test has no delete_pattern; the fallback must still invalidate.
- L70 `InvalidationEventCoverageTests` (class) — Every catalog-changing event must bust the query cache — not just
- L75 `_assert_busts(self, event, **payload)` (method)
- L86 `test_product_created_busts(self)` (method)
- L91 `test_collection_updated_busts(self)` (method)
- L96 `test_stock_out_busts(self)` (method)

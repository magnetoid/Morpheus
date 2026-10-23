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

# api/tests_graphql_cache.py

Symbols in `api/tests_graphql_cache.py`.

- L26 `GraphQLCacheIsolationTests` (class)
- L27 `setUp(self)` (method)
- L40 `_post(self, *, user=None, auth_header='')` (method)
- L48 `_post_query(self, query)` (method)
- L55 `test_anonymous_requests_are_cached(self)` (method)
- L60 `test_cart_query_never_cached(self)` (method)
- L67 `test_shipping_rates_query_never_cached(self)` (method)
- L74 `test_authenticated_request_bypasses_cache_both_ways(self)` (method)
- L91 `test_bearer_token_request_bypasses_cache(self)` (method)
- L96 `test_non_catalog_query_is_not_cached(self)` (method)
- L103 `_post_varying(self, *, currency='', market_pk='', lang='en')` (method)
- L116 `test_currency_varies_the_cache_key(self)` (method)
- L126 `test_market_and_language_vary_the_cache_key(self)` (method)

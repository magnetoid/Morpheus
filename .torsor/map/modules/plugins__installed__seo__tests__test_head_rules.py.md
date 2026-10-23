---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/seo/tests/test_head_rules.py

Symbols in `plugins/installed/seo/tests/test_head_rules.py`.

- L41 `_head(response)` (function)
- L45 `_alternates(head: str)` (function)
- L49 `_graph(head: str)` (function)
- L57 `_product(slug: str, **extra)` (function)
- L71 `ErrorPageHeadTests` (class) — A 404 is not a page: title, description, robots — and nothing else.
- L74 `setUp(self)` (method)
- L77 `_assert_bare_error_head(self, path: str)` (method)
- L92 `test_missing_pages_in_every_language_carry_a_bare_head(self)` (method)
- L102 `test_a_page_number_past_the_end_names_no_live_listing(self)` (method)
- L108 `test_the_error_title_follows_the_language(self)` (method)
- L116 `NoindexPageHeadTests` (class) — A page that asks not to be indexed never names another URL.
- L119 `setUp(self)` (method)
- L122 `test_a_private_page_keeps_its_own_canonical_and_nothing_else(self)` (method)
- L129 `test_internal_search_results_are_noindex_without_a_foreign_canonical(self)` (method)
- L139 `test_a_merchant_noindex_reason_from_the_view_is_honoured(self)` (method)
- L148 `EmptyListingTests` (class) — An empty listing is a soft 404: kept out of the index, links still followed.
- L151 `setUp(self)` (method)
- L154 `test_an_empty_catalogue_is_noindex_follow(self)` (method)
- L160 `test_a_listing_with_items_is_indexable(self)` (method)
- L166 `test_a_view_reported_count_of_zero_holds_a_listing_back(self)` (method)
- L176 `test_an_unreported_count_changes_nothing(self)` (method)
- L184 `AlternatesFollowTheCanonicalTests` (class) — hreflang names the canonical in each language — never the raw request.
- L187 `setUp(self)` (method)
- L190 `test_tracking_parameters_never_reach_an_alternate(self)` (method)
- L199 `test_page_two_keeps_its_page_in_every_language(self)` (method)
- L207 `test_the_graph_describes_the_canonical_url(self)` (method)
- L214 `MarketAlternateTests` (class) — A market is a region; its alternate must name a page that exists on its own.
- L217 `setUp(self)` (method)
- L221 `_market(self, **extra)` (method)
- L235 `test_a_market_without_countries_publishes_no_alternate(self)` (method)
- L241 `test_a_market_whose_parameter_is_consolidated_publishes_no_alternate(self)` (method)
- L245 `test_an_indexable_market_publishes_regional_alternates_and_one_default(self)` (method)
- L261 `PageKindTableTests` (class) — Route names are matched with their namespace: `home` is not one route.
- L264 `test_another_apps_route_named_home_is_not_the_home_page(self)` (method)
- L275 `test_the_storefront_home_is_the_home_page(self)` (method)
- L282 `SignInTitleTests` (class) — Auth pages are named for a person, not after their route.
- L285 `test_the_sign_in_page_says_sign_in(self)` (method)

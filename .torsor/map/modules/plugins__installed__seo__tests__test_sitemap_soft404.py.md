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

# plugins/installed/seo/tests/test_sitemap_soft404.py

Symbols in `plugins/installed/seo/tests/test_sitemap_soft404.py`.

- L23 `_paths()` (function)
- L30 `_product(slug: str, *, status: str='active', **extra)` (function)
- L44 `ListingEntriesTests` (class)
- L45 `setUp(self)` (method)
- L48 `test_an_empty_category_is_left_out_and_a_stocked_one_is_listed(self)` (method)
- L65 `test_an_empty_collection_is_left_out(self)` (method)
- L76 `test_a_vendor_with_nothing_to_show_is_left_out(self)` (method)
- L87 `test_listings_another_app_contributes_put_a_vendor_in(self)` (method)
- L102 `StorefrontEntriesTests` (class) — The storefront's own index pages enter the sitemap only with content.
- L105 `setUp(self)` (method)
- L108 `test_an_empty_store_lists_no_empty_index_page(self)` (method)
- L117 `test_a_stocked_store_lists_its_catalogue_and_vendors(self)` (method)
- L130 `test_the_journal_index_needs_a_live_post(self)` (method)
- L150 `AuthorEntriesTests` (class)
- L151 `setUp(self)` (method)
- L154 `test_an_author_whose_books_are_all_withdrawn_is_left_out(self)` (method)
- L166 `ClaimedCmsPageTests` (class) — A CMS page rendered at another route has ONE url, and that is the sitemap's.
- L169 `setUp(self)` (method)
- L172 `test_the_shipping_policy_page_is_listed_once_at_its_route(self)` (method)
- L187 `DisabledAppEntriesTests` (class) — A route the app no longer serves must leave the sitemap with it.
- L190 `setUp(self)` (method)
- L193 `test_a_disabled_book_vertical_takes_its_urls_along(self)` (method)

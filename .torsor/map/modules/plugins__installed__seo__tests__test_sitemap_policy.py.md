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

# plugins/installed/seo/tests/test_sitemap_policy.py

Symbols in `plugins/installed/seo/tests/test_sitemap_policy.py`.

- L25 `_seo(obj, **fields)` (function)
- L33 `SitemapPolicyTests` (class)
- L35 `setUpTestData(cls)` (method)
- L51 `_locs(self)` (method)
- L54 `test_an_active_product_is_listed(self)` (method)
- L57 `test_a_noindex_page_is_not_asked_to_be_crawled(self)` (method) — Asking Google to crawl a page we then tell it to drop is pure waste.
- L64 `test_the_merchant_can_keep_a_page_out(self)` (method)
- L68 `test_the_merchant_can_override_the_noindex_exclusion(self)` (method) — An explicit choice beats the platform's inference, both ways.
- L73 `test_the_default_is_untouched(self)` (method) — A row that exists for other reasons must not change listing.
- L78 `test_an_active_vendor_is_listed(self)` (method) — `/vendor/<slug>/` is a live storefront page and the docstring lists it.
- L107 `SitemapIndexTests` (class) — robots.txt names `/sitemap-index.xml`, so everything it lists gets fetched.
- L110 `_children(self)` (method)
- L117 `_set_seo_config(self, key, value)` (method)
- L126 `test_every_child_the_index_lists_is_served(self)` (method) — The news sitemap is OFF by default and 404s — the index listed it anyway,
- L135 `test_a_sitemap_the_merchant_enabled_is_listed(self)` (method)
- L139 `test_a_sitemap_the_merchant_disabled_is_not_listed(self)` (method)

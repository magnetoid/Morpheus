---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/booking_marketplace/tests/test_seo_integration.py

Symbols in `plugins/installed/booking_marketplace/tests/test_seo_integration.py`.

- L31 `_head(response)` (function)
- L35 `_host(slug='kotor-boats', **kw)` (function)
- L39 `_experience(vendor, slug, **kw)` (function)
- L53 `HostPageTests` (class)
- L54 `setUp(self)` (method)
- L57 `test_a_host_page_lists_the_hosts_experiences_and_stays(self)` (method)
- L70 `test_a_host_with_nothing_to_offer_stays_out_of_the_index(self)` (method)
- L75 `test_the_directory_and_the_sitemap_count_the_hosts_offers(self)` (method)
- L84 `test_the_page_is_titled_for_hosts_not_publishers(self)` (method)
- L91 `OneGraphPerPageTests` (class)
- L92 `setUp(self)` (method)
- L95 `_graph(self, path)` (method)
- L100 `test_an_experience_page_has_one_graph_with_its_product(self)` (method)
- L111 `test_listings_publish_no_faq_the_page_does_not_show(self)` (method)
- L118 `test_the_hotels_index_faq_is_the_one_on_the_page(self)` (method)
- L127 `ListingRulesTests` (class)
- L128 `setUp(self)` (method)
- L131 `test_a_search_of_the_experiences_is_noindex(self)` (method)
- L136 `test_a_region_with_nothing_to_book_is_noindex_and_left_off_the_index(self)` (method)
- L144 `test_the_hosts_back_office_is_private(self)` (method)
- L155 `test_the_shop_is_headed_as_a_shop(self)` (method)
- L163 `RegionDescriptionTests` (class) — The region pages joined the sitemap in v0.80.0 with no meta description.
- L173 `setUp(self)` (method)
- L176 `_description(self, path)` (method)
- L183 `test_a_region_page_describes_what_it_lists(self)` (method)
- L194 `test_a_long_region_description_stays_snippet_length(self)` (method)
- L207 `test_the_regions_index_names_the_regions_it_lists(self)` (method)
- L218 `SerbianChromeTests` (class) — The header menu and region names were English on every `/sr/` page.
- L221 `test_the_menu_counts_are_translated(self)` (method)
- L237 `test_a_places_fact_labels_are_translated(self)` (method)
- L252 `test_region_names_are_translated(self)` (method)
- L265 `InactiveHostTests` (class)
- L266 `test_a_deactivated_hosts_pages_are_gone(self)` (method)
- L274 `SearchPathTests` (class)
- L275 `test_search_lands_on_the_experiences_when_they_are_the_inventory(self)` (method)
- L281 `test_linked_experience_products_do_not_count_as_a_catalogue(self)` (method)
- L291 `test_a_store_with_a_catalogue_keeps_its_own_search(self)` (method)

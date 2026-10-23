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

# plugins/installed/seo/tests/test_offer_claims.py

Symbols in `plugins/installed/seo/tests/test_offer_claims.py`.

- L28 `_offer(graph)` (function)
- L35 `OfferClaimTests` (class)
- L37 `setUpTestData(cls)` (method)
- L46 `_graph(self)` (method)
- L62 `test_no_shipping_rates_means_no_shipping_claim(self)` (method) — The headline bug. With nothing configured the page said free
- L68 `test_no_store_country_means_no_return_policy_claim(self)` (method) — `applicableCountry` is required on a MerchantReturnPolicy, so a
- L75 `_offer_now(self)` (method)
- L79 `test_a_configured_rate_is_published_at_its_real_price(self)` (method)
- L101 `test_a_carrier_quoted_rate_publishes_no_price(self)` (method) — A live carrier rate is only known at checkout. Quoting a number for
- L111 `test_the_return_window_is_published_once_the_store_has_a_country(self)` (method)
- L125 `AvailabilityTests` (class) — One vocabulary, and it has to reflect the warehouse.
- L129 `setUpTestData(cls)` (method)
- L138 `test_a_product_with_no_stock_rows_is_purchasable(self)` (method) — No inventory tracking means nothing is holding the sale back.
- L144 `test_variants_with_no_stock_rows_are_untracked_not_sold_out(self)` (method) — The bug this shipped with. A store that has never created a single
- L158 `test_an_untracked_variant_keeps_the_product_buyable(self)` (method) — One counted variant at zero must not bury a sibling nobody counts.
- L175 `test_a_product_that_does_not_track_inventory_is_always_purchasable(self)` (method) — `track_inventory=False` is the merchant saying so in as many words.
- L191 `test_a_variant_with_zero_stock_is_out_of_stock(self)` (method) — The check that never ran on a product page: it lived behind an
- L206 `test_a_backorder_variant_is_still_buyable(self)` (method)
- L219 `test_an_archived_product_is_discontinued(self)` (method)
- L225 `test_the_markup_repeats_whatever_the_warehouse_says(self)` (method) — The whole point of one vocabulary: feed, Open Graph and JSON-LD

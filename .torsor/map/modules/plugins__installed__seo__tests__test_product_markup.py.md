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

# plugins/installed/seo/tests/test_product_markup.py

Symbols in `plugins/installed/seo/tests/test_product_markup.py`.

- L26 `ProductMarkupFromRenderedPayloadTests` (class) — The dict-plus-model path the product page actually uses.
- L30 `setUpTestData(cls)` (method)
- L47 `test_the_rendered_payload_alone_still_produces_a_valid_offer(self)` (method) — The floor: no model row, still a usable listing.
- L57 `test_the_model_row_supplies_what_a_dict_cannot_carry(self)` (method) — The fix. Identifiers are the clearest case: a GTIN/ISBN is what lets
- L73 `test_price_and_availability_still_come_from_what_was_rendered(self)` (method) — The model row must not override the payload: the view loads the
- L81 `test_an_out_of_stock_product_does_not_advertise_in_stock(self)` (method) — The stock check only ran on the ORM path, so every product page —
- L88 `test_availability_matches_the_channel_feeds(self)` (method) — One vocabulary. Markup that disagrees with the feed is a Merchant
- L98 `ProductGraphOnThePageTests` (class) — End to end: what the page's `@graph` carries for a product.
- L102 `setUpTestData(cls)` (method)
- L111 `_graph(self)` (method)
- L128 `test_the_product_node_is_built_from_both_sources(self)` (method)
- L138 `test_exactly_one_node_claims_to_be_the_product(self)` (method)
- L144 `RatingClaimTests` (class) — A star rating is a claim about what the page shows.
- L148 `setUpTestData(cls)` (method)
- L175 `test_the_rating_counts_only_reviews_the_page_shows(self)` (method) — The aggregate counted every row while the Review nodes filtered to
- L187 `VariantMarkupTests` (class) — A product sold in several versions is a group, and says so.
- L197 `setUpTestData(cls)` (method)
- L222 `_node(self)` (method)
- L225 `test_a_multi_version_product_is_a_product_group(self)` (method)
- L231 `test_each_variant_carries_its_own_price(self)` (method)
- L236 `test_the_group_says_what_it_varies_by(self)` (method) — Print vs digital is a material difference; claiming an axis the
- L241 `test_a_single_variant_is_not_a_group(self)` (method) — A chooser for one option is a chooser the shopper does not have.
- L248 `test_a_variant_out_of_stock_is_not_advertised_as_available(self)` (method) — Every member used to be hardcoded InStock, so a group whose only
- L264 `SalePriceTests` (class) — A discount is only a discount if the old price was higher.
- L268 `setUpTestData(cls)` (method)
- L277 `test_a_reduced_product_publishes_its_previous_price(self)` (method)
- L288 `test_a_compare_at_price_that_is_not_higher_is_not_a_sale(self)` (method) — A leftover compare-at price equal to the price would advertise a
- L298 `test_no_compare_at_price_means_no_claim(self)` (method)
- L303 `DeferredFieldTests` (class) — A view that loads a product with `.only()` must not cost it its markup.
- L315 `setUpTestData(cls)` (method)
- L325 `test_a_deferred_money_field_does_not_lose_the_product_node(self)` (method)
- L339 `test_the_full_row_still_publishes_the_sale(self)` (method)
- L347 `BookVariantTypeTests` (class) — A book sold in several editions is still a group.
- L357 `setUpTestData(cls)` (method)
- L376 `test_a_multi_edition_book_keeps_its_group_type_beside_a_book_node(self)` (method)

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

# plugins/installed/booking_marketplace/tests/test_listing_products.py

Symbols in `plugins/installed/booking_marketplace/tests/test_listing_products.py`.

- L25 `ListingProductTests` (class)
- L26 `setUp(self)` (method)
- L40 `test_a_listing_gets_one_service_product_with_its_fields(self)` (method)
- L53 `test_an_archived_good_with_the_same_slug_and_name_is_reused(self)` (method)
- L65 `test_a_different_product_on_the_slug_is_left_alone(self)` (method)
- L78 `test_product_edits_flow_to_the_listing(self)` (method)
- L89 `test_the_product_page_redirects_to_the_booking_page(self)` (method)
- L95 `test_saving_the_product_updates_the_listing_without_a_call(self)` (method)
- L102 `test_a_host_edit_reaches_the_product(self)` (method)
- L112 `test_an_archived_product_stays_archived_when_its_listing_is_saved(self)` (method)
- L124 `test_a_listing_saved_in_the_editor_gets_its_product(self)` (method)
- L147 `test_a_renamed_product_slug_still_leads_to_the_booking_page(self)` (method)
- L159 `test_graphql_has_no_product_page_for_a_service(self)` (method)
- L166 `test_a_bulk_archive_on_products_reaches_the_listing(self)` (method)
- L180 `test_clearing_the_products_host_keeps_the_listing_in_step(self)` (method)
- L192 `test_an_active_same_named_product_is_never_converted(self)` (method)
- L206 `ListingProductPhotoAndSlugTests` (class)
- L207 `setUp(self)` (method)
- L223 `_photo(self, name)` (method)
- L232 `test_the_listing_photos_become_the_product_images_in_order(self)` (method)
- L255 `test_a_reused_product_keeps_its_own_photos(self)` (method)
- L270 `test_an_unrelated_product_on_the_fallback_slug_is_left_alone(self)` (method)
- L284 `test_deleting_a_product_photo_keeps_the_listings_file(self)` (method)

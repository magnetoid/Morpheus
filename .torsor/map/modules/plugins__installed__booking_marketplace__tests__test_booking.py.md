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

# plugins/installed/booking_marketplace/tests/test_booking.py

Symbols in `plugins/installed/booking_marketplace/tests/test_booking.py`.

- L28 `_vendor()` (function)
- L34 `_service(vendor, **kw)` (function)
- L46 `_future(days=2)` (function)
- L50 `ModelTests` (class)
- L51 `test_create_chain(self)` (method)
- L57 `PricingCapacityTests` (class)
- L58 `test_totals_with_12pct_fee(self)` (method)
- L67 `test_capacity_guard_blocks_overbooking(self)` (method)
- L76 `test_requires_approval_is_pending(self)` (method)
- L83 `test_past_date_rejected(self)` (method)
- L93 `test_weekday_restriction(self)` (method)
- L101 `_post(svc, data)` (function)
- L111 `MarketplaceFlowTests` (class) — Marketplace mode WITH a payment step — the only state that may confirm.
- L119 `test_valid_booking_created(self)` (method)
- L135 `test_missing_fields_rejected(self)` (method)
- L142 `ListingFlowTests` (class)
- L143 `test_enquiry_created_no_booking(self)` (method)
- L150 `test_enquiry_requires_email(self)` (method)
- L156 `EarningsTests` (class)
- L157 `setUp(self)` (method)
- L167 `test_earnings_summary(self)` (method)
- L179 `DisabledByDefaultTests` (class)
- L180 `test_plugin_ships_disabled(self)` (method)
- L186 `ReviewTests` (class)
- L187 `setUp(self)` (method)
- L202 `test_can_review_only_with_booking(self)` (method)
- L206 `test_create_review_is_gated(self)` (method)
- L213 `test_one_review_per_user_updates(self)` (method)
- L219 `test_rating_bounds(self)` (method)
- L223 `test_summary(self)` (method)
- L229 `test_create_review_resyncs_denormalised_rating(self)` (method)
- L240 `I18nTests` (class) — Serbian is served at `/sr/…`, not by content negotiation.
- L250 `test_serbian_nav_translated(self)` (method)
- L255 `test_english_default(self)` (method)
- L260 `test_serbian_list_heading(self)` (method)
- L267 `ExperienceSearchTests` (class)
- L268 `test_text_search_filters(self)` (method)
- L285 `PlacesTests` (class)
- L286 `setUp(self)` (method)
- L306 `test_places_index_lists_places(self)` (method)
- L311 `test_place_detail_lists_local_experiences(self)` (method)
- L316 `test_unknown_place_404(self)` (method)
- L320 `test_homepage_features_places(self)` (method)
- L326 `RegionDirectoryTests` (class)
- L327 `setUp(self)` (method)
- L346 `test_regions_index_lists_regions(self)` (method)
- L351 `test_region_detail_filters_by_region(self)` (method)
- L357 `test_unknown_region_404(self)` (method)
- L363 `RichExperienceTests` (class)
- L364 `setUp(self)` (method)
- L384 `test_card_shows_rich_fields(self)` (method)
- L392 `test_detail_shows_highlights_and_included(self)` (method)
- L401 `test_detail_serbian_labels(self)` (method)
- L407 `HomepageExperiencesTests` (class)
- L408 `test_featured_experiences_tag_orders_bestsellers_first(self)` (method)
- L439 `test_homepage_renders_experiences(self)` (method)
- L452 `HostUITests` (class)
- L453 `setUp(self)` (method)
- L463 `_req(self, method, path, data=None, user=None)` (method)
- L470 `test_non_host_sees_prompt(self)` (method)
- L477 `test_create_service_with_availability(self)` (method)
- L502 `test_cannot_edit_other_hosts_service(self)` (method)
- L515 `test_booking_action_confirm(self)` (method)

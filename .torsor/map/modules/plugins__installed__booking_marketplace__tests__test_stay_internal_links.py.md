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

# plugins/installed/booking_marketplace/tests/test_stay_internal_links.py

Symbols in `plugins/installed/booking_marketplace/tests/test_stay_internal_links.py`.

- L22 `RelatedStaysServiceTests` (class)
- L24 `setUpTestData(cls)` (method)
- L32 `_hotel(cls, name, town, region, star, **kw)` (method)
- L45 `test_related_excludes_self_and_other_regions(self)` (method)
- L53 `test_same_town_comes_before_the_wider_region(self)` (method)
- L57 `test_inactive_hotel_and_inactive_vendor_are_excluded(self)` (method)
- L65 `test_limit_is_honoured(self)` (method)
- L71 `NearbyPlacesServiceTests` (class)
- L73 `setUpTestData(cls)` (method)
- L87 `test_returns_only_places_in_the_hotels_region(self)` (method)
- L91 `test_inactive_place_excluded(self)` (method)
- L95 `test_regionless_hotel_gets_nothing(self)` (method)
- L101 `StayDetailRendersLinksTests` (class)
- L103 `setUpTestData(cls)` (method)
- L132 `test_page_links_to_sibling_hotel_and_nearby_place(self)` (method)
- L141 `test_page_renders_the_cancellation_policy(self)` (method)
- L145 `test_page_does_not_link_to_itself(self)` (method)
- L152 `PolicyResolutionTests` (class) — The policies dict shape lives in the plugin (POLICY_LABELS + _policies),
- L157 `test_canonical_order_regardless_of_stored_order(self)` (method)
- L161 `test_empty_and_missing_values_are_skipped(self)` (method)
- L165 `test_unknown_key_is_humanised_and_kept(self)` (method)
- L172 `test_none_is_safe(self)` (method)
- L176 `PolicyRenderIsDataDrivenTests` (class)
- L177 `test_a_policy_key_the_theme_never_names_still_renders(self)` (method) — Proof the theme is not hardcoded to the four seeded keys: an

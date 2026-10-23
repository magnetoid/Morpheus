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

# plugins/installed/booking_marketplace/tests/test_ai_feed.py

Symbols in `plugins/installed/booking_marketplace/tests/test_ai_feed.py`.

- L33 `AiFeedContributionTests` (class)
- L35 `setUpTestData(cls)` (method)
- L57 `_items(self, **kw)` (method)
- L61 `test_experiences_and_stays_appear_in_the_feed(self)` (method)
- L67 `test_experience_carries_a_priced_offer(self)` (method)
- L75 `test_stay_is_a_hotel_with_a_price_floor_not_a_fixed_price(self)` (method) — `price_from` is a nightly floor — quoting it as a fixed `price`
- L85 `test_inactive_rows_are_excluded(self)` (method)
- L90 `test_rows_of_an_inactive_vendor_are_excluded(self)` (method)
- L95 `test_pagination_walks_the_contributed_tail_without_repeating(self)` (method)
- L105 `test_positions_are_sequential_across_the_window(self)` (method)
- L110 `AiFeedRatingClaimTests` (class) — A rating in the feed is a claim to every AI crawler, so only reviews a
- L122 `setUpTestData(cls)` (method)
- L145 `_item(self, name)` (method)
- L149 `_guest_review(self, rating, email)` (method) — A review through the real gate: a booking first, then create_review.
- L164 `test_denormalised_columns_alone_publish_no_rating(self)` (method)
- L167 `test_seeded_reviews_publish_no_rating(self)` (method)
- L174 `test_verified_reviews_are_published_and_counted_alone(self)` (method)
- L185 `test_a_stay_never_claims_a_guest_rating(self)` (method) — Property has no review model at all; its columns are editorial.
- L192 `test_rating_costs_no_query_per_experience(self)` (method) — The feed annotates once. verified_rating's per-row fallback is

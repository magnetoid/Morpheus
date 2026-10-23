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

# plugins/installed/booking_marketplace/tests/test_hotel_blurbs.py

Symbols in `plugins/installed/booking_marketplace/tests/test_hotel_blurbs.py`.

- L26 `BlurbGeneratorTests` (class)
- L27 `test_same_class_hotels_get_distinct_descriptions(self)` (method) — Two 4-star Podgorica hotels — identical everything but the name —
- L36 `test_only_real_amenities_are_named(self)` (method) — The blurb is a public claim — it must not invent a spa. A hotel
- L44 `test_at_most_three_features_named(self)` (method)
- L56 `test_no_features_falls_back_to_a_clean_sentence(self)` (method)
- L62 `test_typical_blurb_lands_in_the_meta_length_window(self)` (method)
- L69 `test_feature_phrase_joins_naturally(self)` (method)
- L78 `RefreshCommandTests` (class)
- L80 `setUpTestData(cls)` (method)
- L83 `_hotel(self, name, town, star, ptype, ptype_label, amenities, short)` (method)
- L95 `test_legacy_rows_are_rewritten_edited_rows_are_kept(self)` (method)
- L119 `test_second_run_changes_nothing(self)` (method)
- L136 `test_dry_run_writes_nothing(self)` (method)

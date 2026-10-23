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

# plugins/installed/booking_marketplace/management/commands/seed_hotels_montenegro.py

Symbols in `plugins/installed/booking_marketplace/management/commands/seed_hotels_montenegro.py`.

- L394 `_stable_hash(key: str)` (function) — Deterministic, non-cryptographic hash used only to seed jitter/rating
- L400 `_jitter(lat: float, lng: float, key: str, spread: float=0.008)` (function) — Deterministic tiny offset (~<=500m) so same-town pins don't stack.
- L408 `_rating_and_reviews(key: str, star: int)` (function) — Deterministic representative rating (~4.0-4.9) and review count.
- L416 `_rate_for(star: int, ptype: str, region: str, tier_index: int)` (function) — Representative nightly base rate, scaled by star / property type /
- L426 `_rooms_for(star: int, ptype: str, region: str)` (function) — 2-4 representative RoomType specs, scaled to class.
- L457 `_base_amenities(ptype: str)` (function) — Amenities implied by property type alone, regardless of star/region.
- L473 `_star_amenities(star: int, ptype: str)` (function) — Amenities implied by star class (higher star -> more facilities).
- L491 `_region_amenities(star: int, ptype: str, region: str)` (function) — Amenities implied by being on the coast (sea view / beachfront).
- L505 `_amenities_for(star: int, ptype: str, region: str)` (function) — Representative hotel-level amenity slugs, fitting the class.
- L519 `_policies_for(star: int)` (function)
- L551 `_feature_phrase(amenities)` (function) — Up to three of the hotel's real, guest-salient amenities, as a phrase
- L563 `_legacy_short_blurb(town: str, star: int, ptype_label: str)` (function) — The pre-v0.73.3 short_description — tier + type + town only, which
- L572 `_blurb_for(name: str, town: str, star: int, ptype_label: str, amenities)` (function) — (short_description, description) for one hotel.
- L593 `_field_values(name: str, town: str, star: int, ptype: str)` (function) — Compute every derived Property field for one hotel (pure function).
- L625 `_backfill_property(prop, values: dict)` (function) — Fill fields still empty on a pre-existing row — never clobber
- L649 `_create_room_types(prop, star: int, ptype: str, region: str, room_type_model)` (function) — Create the class-driven RoomTypes for a brand-new property. No-op if
- L673 `Command` (class)
- L676 `handle(self, *args, **opts)` (method)

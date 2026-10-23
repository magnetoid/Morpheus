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

# plugins/installed/booking_marketplace/templatetags/booking_tags.py

Symbols in `plugins/installed/booking_marketplace/templatetags/booking_tags.py`.

- L18 `featured_experiences(limit=8)` (function) — Top active experiences — bestsellers first, then by rating / reviews.
- L33 `featured_places(limit=6)` (function) — Destinations for the homepage strip — featured first, then sort order.
- L45 `booking_listing_mode()` (function) — Enquiry mode flag (opt-in), for templates that branch on price visibility.
- L51 `booking_enquiry_only()` (function) — Whether a submit captures an enquiry rather than confirming a booking.
- L64 `dictkey(d, key)` (function) — Look up d[key] with a variable key (templates can't do d[var]).
- L93 `_cat_href(slug)` (function)
- L98 `booking_categories()` (function) — Live categories (name + count) — the single category source.
- L106 `search_bar(context, variant='bar')` (function) — Everything booking_marketplace/_search.html shows (search_page.bar_context).
- L114 `home_categories()` (function) — Category band tiles: label + glyph + live count + filtered link.
- L132 `home_testimonials()` (function) — Guest reviews (rating ≥4 with body text) from a real booking, newest first.
- L163 `listing_rating(service)` (function) — (count, average) of a listing's verified reviews, the only rating a card or
- L177 `verified_review_summary()` (function) — {'count', 'avg'} over every verified review, for the homepage's guest section.
- L189 `listing_text(value)` (function) — A listing's text as HTML, the way the product page shows a product's.

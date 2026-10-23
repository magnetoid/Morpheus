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

# plugins/installed/booking_marketplace/views.py

Symbols in `plugins/installed/booking_marketplace/views.py`.

- L41 `listing_mode()` (function) — Enquiry mode (opt-in; no prices/payments). Defaults to False (marketplace mode).
- L46 `payments_ready()` (function) — True once a payment step gates confirmation (see settings.BOOKING_PAYMENTS_READY).
- L51 `takes_enquiry_only()` (function) — Whether a submit must capture an ENQUIRY rather than confirm a booking.
- L63 `_crumbs(request, *trail)` (function) — `breadcrumb_items` for the head's BreadcrumbList: Home, then `(name, path)` pairs.
- L77 `_image_url(obj)` (function)
- L95 `_sort(request, *, has_query: bool)` (function)
- L102 `_ranked(rows, matches, sort: str)` (function) — `rows` the search matched; best first, top picks then names breaking ties, when asked.
- L112 `_searched(request, q: str, count: int)` (function) — SEARCH_PERFORMED, as the storefront's own search fires it: search trends, the
- L121 `services_list(request)` (function) — Browse bookable experiences: what the search bar asked for, best match first.
- L193 `products_list(request)` (function) — Browse product-kind listings (the Shop); a search shows its best matches first.
- L240 `suggest(request)` (function) — Suggestions while a visitor types in the search bar: JSON for search.js, never indexed.
- L256 `places_index(request)` (function) — Directory of Montenegro destinations (editorial), grouped by region.
- L312 `_place_meta_description(place)` (function) — A 150–160 char meta description: the curated summary, topped up from the
- L321 `place_detail(request, slug)` (function)
- L358 `_lead_with_names(lead: str, names, limit: int=155)` (function) — `lead` followed by as many of `names` as fit a search snippet.
- L372 `regions_index(request)` (function) — Directory of Montenegro regions with experiences, each with a count + a cover.
- L427 `region_detail(request, region)` (function)
- L477 `service_detail(request, slug)` (function)
- L549 `_similar_services(service, limit=4)` (function) — Other active experiences for the 'Similar experiences' rail — same region
- L574 `post_review(request, slug)` (function)
- L591 `_parse_selection(request)` (function) — Pull tier_<id>=qty and addon_<id>=qty out of POST into two dicts.
- L602 `_create_booking(request, service)` (function)
- L630 `_submit_enquiry(request, service)` (function)
- L663 `_detail_url(service)` (function)
- L667 `events_index(request)` (function) — Calendar of Montenegro events, grouped by month.
- L724 `event_detail(request, slug)` (function)

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

# plugins/installed/booking_marketplace/seo_jsonld.py

Symbols in `plugins/installed/booking_marketplace/seo_jsonld.py`.

- L21 `_abs(request, path: str)` (function)
- L30 `faq_node(pairs, url: str='')` (function) — FAQPage from `[{q, a}]` — only for questions the page itself shows.
- L51 `_destination_node(place, *, url: str, request=None)` (function)
- L85 `place_nodes(place, *, url: str, request=None)` (function) — TouristDestination (+ geo/address), and its FAQPage when the page shows one.
- L94 `_offer(service, url: str)` (function)
- L104 `_product_node(service, *, url: str, request=None, with_prices=True)` (function)
- L145 `_trip_node(service, *, url: str, request=None, with_prices=True)` (function) — TouristTrip: the experience as a trip, its itinerary an ordered list of steps.
- L177 `experience_nodes(service, *, url: str, request=None, with_prices=True)` (function) — Product (+ Offer, verified rating), TouristTrip (+ itinerary) and the visible FAQPage.
- L195 `_hotel_node(prop, *, url: str, request=None, with_prices=True)` (function) — Hotel (a LodgingBusiness). Only emits fields that are also visible on the
- L263 `property_nodes(prop, *, url: str, request=None, with_prices=True)` (function) — Hotel (+ geo, address, amenities, star rating, room Offers).
- L268 `event_nodes(event, *, url: str, request=None)` (function) — schema.org/Event for a single event page.
- L312 `listing_items(rows, *, request)` (function) — `jsonld_items` for a listing page: `[(name, path, image_url)]` → the head's ItemList.

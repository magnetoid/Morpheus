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

# plugins/installed/booking_marketplace/services.py

Symbols in `plugins/installed/booking_marketplace/services.py`.

- L25 `BookingError` (class) — Raised when a booking can't be made (bad input / no capacity).
- L29 `_weekdays(service)` (function)
- L34 `booked_guests(service, date, time=None)` (function) — Guests already holding a spot on `date` (pending + confirmed).
- L47 `available_dates(service, *, days: int=30, limit: int=30)` (function) — Upcoming dates with remaining capacity, soonest first.
- L60 `_start_times(service)` (function) — Sorted distinct 'HH:MM' departure strings, or [None] when the service
- L69 `available_sessions(service, *, days: int=30, limit: int=30)` (function) — Upcoming dates, each with its bookable departures + remaining capacity.
- L91 `bookable_on(services, day)` (function) — The listings in `services` a guest can still book on `day`, in the given order.
- L135 `create_booking(service, *, booking_date, guests: int=0, name: str, email: str, phone: str='', notes: str='', time: str='', tiers=None, addons=None, user=None)` (function) — Create a confirmed (or pending) booking with server-derived totals.
- L233 `submit_enquiry(service, *, email: str, name: str='', phone: str='', preferred_date=None, guests=None, message: str='', time: str='', tiers=None, addons=None, user=None)` (function) — Capture a 'Contact for price' lead (listing mode). Anon-allowed.
- L306 `_safe_qty(v)` (function)
- L316 `price_quote(service, *, tiers: dict, addons: dict)` (function) — Server-derived quote for a booking selection. Single source of truth.
- L411 `can_review(service, user)` (function) — True if `user` has a confirmed/completed booking for `service`.
- L422 `review_summary(service)` (function) — {'avg': float|None, 'count': int} for a service's reviews.
- L431 `_verified(prefix: str='')` (function) — The booking is the evidence a review is a guest's: `create_review`
- L439 `verified_reviews(service)` (function) — The reviews a public claim may rest on.
- L452 `with_verified_rating(qs)` (function) — Annotate `verified_count` / `verified_avg` on a BookableService
- L462 `verified_rating(service)` (function) — (count, average) over `verified_reviews` — the only rating structured
- L471 `create_review(service, *, user, rating, title='', body='')` (function) — Create/update a guest's review. Gated on a real booking (server-side).
- L515 `active_categories()` (function) — Categories that currently have ≥1 active experience, with counts.
- L546 `live_regions()` (function) — Regions with a live experience, in REGIONS order, with counts: the search bar's Where.

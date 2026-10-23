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

# plugins/installed/booking_marketplace/models.py

Symbols in `plugins/installed/booking_marketplace/models.py`.

- L49 `BookableService` (class) — An experience a host offers — booked by date + guest count.
- L149 `__str__(self)` (method)
- L153 `AvailabilityWindow` (class) — A weekday on which the experience runs (optional start/end time).
- L181 `__str__(self)` (method)
- L185 `Booking` (class) — A customer's reservation of an experience for a date + guest count.
- L224 `__str__(self)` (method)
- L228 `Enquiry` (class) — A "Contact for price" lead captured in listing mode (anon-allowed).
- L268 `__str__(self)` (method)
- L272 `ServiceReview` (class) — A guest review of an experience — gated on a real confirmed/completed
- L303 `__str__(self)` (method)
- L307 `Place` (class) — A Montenegro destination (town / area) with editorial content.
- L365 `__str__(self)` (method)
- L369 `ServiceImage` (class) — Gallery image for an experience (beyond the single cover `image`).
- L381 `__str__(self)` (method)
- L385 `PricingTier` (class) — A per-person price band for an experience (Adult / Child / …).
- L404 `__str__(self)` (method)
- L408 `AddOn` (class) — An optional paid extra for an experience (gear, pickup, photos).
- L427 `__str__(self)` (method)
- L488 `Property` (class) — A hotel / accommodation, owned by a catalog.Vendor.
- L525 `__str__(self)` (method)
- L528 `recalc_price_from(self, save=True)` (method) — Set price_from to the cheapest active room's base_rate.
- L538 `RoomType` (class) — A bookable room category within a Property.
- L567 `__str__(self)` (method)
- L571 `StayBooking` (class) — A reservation of a RoomType for a check-in→check-out date range.
- L613 `__str__(self)` (method)
- L617 `StayEnquiry` (class) — A 'Contact for price' accommodation lead (listing mode; anon-allowed).
- L652 `__str__(self)` (method)
- L656 `PropertyImage` (class) — Gallery image for a Property.
- L669 `__str__(self)` (method)
- L682 `Event` (class) — A Montenegro event — festival, carnival, regatta, concert season.
- L747 `__str__(self)` (method)
- L751 `when_display(self)` (method) — Human timing: the editorial label, else the month name, else ''.

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

# plugins/installed/booking_marketplace/stays.py

Symbols in `plugins/installed/booking_marketplace/stays.py`.

- L33 `_as_date(v)` (function) — Coerce a date / datetime / ISO 'YYYY-MM-DD' string to a date.
- L45 `nights_between(check_in, check_out)` (function)
- L57 `quote_stay(room_type, *, check_in, check_out, rooms=1, adults=2, children=0)` (function) — Server-derived quote for a stay. Raises BookingError on bad input.
- L108 `room_availability(room_type, check_in, check_out)` (function) — Rooms of `room_type` free for every night in [check_in, check_out).
- L136 `create_stay_booking(*, room_type, customer=None, customer_name, customer_email, customer_phone='', check_in, check_out, rooms=1, adults=2, children=0, notes='')` (function) — Create a confirmed stay booking with server-derived totals.
- L207 `submit_stay_enquiry(*, property, room_type=None, customer=None, name='', email, phone='', check_in=None, check_out=None, rooms=None, adults=None, children=None, message='')` (function) — Capture a 'Contact for price' accommodation lead (listing mode; anon-allowed).
- L267 `nearby_places(prop, *, limit=6)` (function) — Destination guides in this hotel's region.
- L280 `related_stays(prop, *, limit=6)` (function) — Other active hotels near this one: the same town first, then the wider

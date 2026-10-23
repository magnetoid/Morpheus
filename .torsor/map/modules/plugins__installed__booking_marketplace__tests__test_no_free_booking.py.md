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

# plugins/installed/booking_marketplace/tests/test_no_free_booking.py

Symbols in `plugins/installed/booking_marketplace/tests/test_no_free_booking.py`.

- L42 `_future(days: int)` (function)
- L46 `_vendor(slug='free-booking-vendor')` (function)
- L52 `StayConfirmationGateTests` (class)
- L53 `setUp(self)` (method)
- L69 `_post(self)` (method)
- L85 `test_visible_prices_do_not_by_themselves_allow_a_free_confirmed_stay(self)` (method) — The exact production configuration that took the EUR 1,945 hold.
- L92 `test_confirmed_stay_allowed_once_payments_are_ready(self)` (method)
- L97 `test_listing_mode_still_only_enquires_even_when_payments_are_ready(self)` (method)
- L103 `ExperienceConfirmationGateTests` (class)
- L104 `setUp(self)` (method)
- L113 `_post(self)` (method)
- L126 `test_visible_prices_do_not_by_themselves_allow_a_free_confirmed_booking(self)` (method) — The exact production configuration that took 15 real unpaid bookings.
- L133 `test_confirmed_booking_allowed_once_payments_are_ready(self)` (method)
- L138 `HonestCallToActionTests` (class) — The button must not promise what the submit does not do.
- L141 `setUp(self)` (method)
- L158 `test_stay_cta_does_not_say_book_now_while_it_only_enquires(self)` (method)

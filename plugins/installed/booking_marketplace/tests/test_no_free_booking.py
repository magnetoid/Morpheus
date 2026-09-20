"""A confirmed booking holds inventory, so it must never be created for free.

What went wrong (found live, 2026-08-12): `BOOKING_LISTING_MODE` was driving two
unrelated things at once — whether prices are *visible*, and whether a submit
creates a *confirmed* booking. Someone turned it off to show prices, which
silently also armed confirmation. But neither `create_booking` nor
`create_stay_booking` has any payment step (stays.py still says "Phase 1: no
payment step yet"), and both write `status='confirmed'` and hold inventory under
a row lock.

Production ran that way and accumulated 15 real unpaid experience bookings from
live consumer addresses plus one EUR 1,945.92 hotel hold — real people told they
were booked, no money taken, a host's rooms blocked at no cost.

`BOOKING_PAYMENTS_READY` is the missing half: it gates *confirmation* alone, so
prices can stay visible while nothing can be booked for free. These tests exist
so the two concerns can never be re-conflated. **If one fails, do not "fix" it by
relaxing the assertion — a red here means the site can take free reservations.**
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import (
    BookableService,
    Booking,
    Enquiry,
    Property,
    RoomType,
    StayBooking,
    StayEnquiry,
)
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin


def _future(days: int) -> str:
    return (datetime.date.today() + datetime.timedelta(days=days)).isoformat()


def _vendor(slug='free-booking-vendor'):
    from plugins.installed.catalog.models import Vendor

    return Vendor.objects.create(name='Guard Vendor', slug=slug, is_active=True)


class StayConfirmationGateTests(TestCase):
    def setUp(self):
        vendor = _vendor()
        self.prop = Property.objects.create(
            vendor=vendor, name='Guard Hotel', slug='guard-hotel', is_active=True
        )
        self.room = RoomType.objects.create(
            property=self.prop,
            name='Double',
            slug='guard-double',
            base_rate=Money(Decimal('100'), 'EUR'),
            max_occupancy=3,
            max_adults=2,
            max_children=1,
            room_count=5,
        )

    def _post(self):
        return self.client.post(
            reverse('booking_marketplace:stay_book', args=['guard-hotel']),
            {
                'room_type': str(self.room.id),
                'check_in': _future(10),
                'check_out': _future(12),
                'rooms': 1,
                'adults': 2,
                'children': 0,
                'name': 'Ana',
                'email': 'ana@example.com',
            },
        )

    @override_settings(BOOKING_LISTING_MODE=False, BOOKING_PAYMENTS_READY=False)
    def test_visible_prices_do_not_by_themselves_allow_a_free_confirmed_stay(self):
        """The exact production configuration that took the EUR 1,945 hold."""
        self._post()
        self.assertEqual(StayBooking.objects.count(), 0, 'free confirmed stay booking created')
        self.assertEqual(StayEnquiry.objects.count(), 1)

    @override_settings(BOOKING_LISTING_MODE=False, BOOKING_PAYMENTS_READY=True)
    def test_confirmed_stay_allowed_once_payments_are_ready(self):
        self._post()
        self.assertEqual(StayBooking.objects.count(), 1)

    @override_settings(BOOKING_LISTING_MODE=True, BOOKING_PAYMENTS_READY=True)
    def test_listing_mode_still_only_enquires_even_when_payments_are_ready(self):
        self._post()
        self.assertEqual(StayBooking.objects.count(), 0)
        self.assertEqual(StayEnquiry.objects.count(), 1)


class ExperienceConfirmationGateTests(TestCase):
    def setUp(self):
        self.service = BookableService.objects.create(
            vendor=_vendor('exp-guard-vendor'),
            name='Guard Tour',
            slug='guard-tour',
            price=50,
            is_active=True,
        )

    def _post(self):
        return self.client.post(
            f'/bookings/{self.service.slug}/',
            {
                'booking_date': _future(10),
                'guests': 2,
                'name': 'Ana',
                'email': 'ana@example.com',
                'preferred_date': _future(10),
            },
        )

    @override_settings(BOOKING_LISTING_MODE=False, BOOKING_PAYMENTS_READY=False)
    def test_visible_prices_do_not_by_themselves_allow_a_free_confirmed_booking(self):
        """The exact production configuration that took 15 real unpaid bookings."""
        self._post()
        self.assertEqual(Booking.objects.count(), 0, 'free confirmed booking created')
        self.assertEqual(Enquiry.objects.count(), 1)

    @override_settings(BOOKING_LISTING_MODE=False, BOOKING_PAYMENTS_READY=True)
    def test_confirmed_booking_allowed_once_payments_are_ready(self):
        self._post()
        self.assertEqual(Booking.objects.count(), 1)


class HonestCallToActionTests(MontenegroThemeMixin, TestCase):
    """The button must not promise what the submit does not do."""

    def setUp(self):
        vendor = _vendor('cta-vendor')
        self.prop = Property.objects.create(
            vendor=vendor, name='CTA Hotel', slug='cta-hotel', is_active=True
        )
        RoomType.objects.create(
            property=self.prop,
            name='Double',
            slug='cta-double',
            base_rate=Money(Decimal('100'), 'EUR'),
            max_occupancy=3,
            max_adults=2,
            max_children=1,
            room_count=5,
        )

    @override_settings(BOOKING_LISTING_MODE=False, BOOKING_PAYMENTS_READY=False)
    def test_stay_cta_does_not_say_book_now_while_it_only_enquires(self):
        html = Client().get('/hotels/cta-hotel/').content.decode()
        self.assertNotIn('Book now', html, '"Book now" promises a booking that is not created')
        self.assertIn('Request to book', html)

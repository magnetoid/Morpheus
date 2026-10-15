"""A date keeps the experiences a guest can still book that day (services.bookable_on).

The search bar sent `date=` and nothing read it. The rule is available_sessions' for
one day: the listing runs that weekday (no windows: every day) and a departure has a
seat left — capacity minus that day's pending and confirmed guests, per departure time
when it has times, for the whole day when it has none.
"""

from __future__ import annotations

import datetime

from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import (
    AvailabilityWindow,
    BookableService,
    Booking,
)
from plugins.installed.booking_marketplace.services import available_sessions, bookable_on
from plugins.installed.catalog.models import Vendor


class BookableOnTests(TestCase):
    def setUp(self):
        self.vendor = Vendor.objects.create(name='Host', slug='host', is_active=True)
        self.day = timezone.localdate() + datetime.timedelta(days=3)
        weekday = self.day.weekday()

        self._listing('every-day')
        self._window(self._listing('another-weekday'), (weekday + 1) % 7)
        self._window(self._listing('that-weekday'), weekday)
        self._book(self._listing('full-day', capacity=2), guests=2)
        two = self._listing('one-departure-left', capacity=2)
        self._window(two, weekday, datetime.time(9, 0))
        self._window(two, weekday, datetime.time(14, 0))
        self._book(two, guests=2, slot='09:00')
        both = self._listing('both-departures-full', capacity=2)
        self._window(both, weekday, datetime.time(9, 0))
        self._window(both, weekday, datetime.time(14, 0))
        self._book(both, guests=2, slot='09:00')
        self._book(both, guests=2, slot='14:00')
        self._book(self._listing('cancelled-booking', capacity=2), guests=2, status='cancelled')

    def _listing(self, slug, capacity=4):
        return BookableService.objects.create(
            vendor=self.vendor,
            name=slug,
            slug=slug,
            price=Money(50, 'EUR'),
            daily_capacity=capacity,
        )

    def _window(self, listing, weekday, start=None):
        AvailabilityWindow.objects.create(service=listing, weekday=weekday, start_time=start)

    def _book(self, listing, *, guests, slot='', status='confirmed'):
        Booking.objects.create(
            service=listing,
            customer_name='Guest',
            customer_email='guest@example.com',
            booking_date=self.day,
            time_slot=slot,
            guests=guests,
            status=status,
        )

    def test_the_rule(self):
        kept = [s.slug for s in bookable_on(BookableService.objects.order_by('slug'), self.day)]
        self.assertEqual(
            kept, ['cancelled-booking', 'every-day', 'one-departure-left', 'that-weekday']
        )

    def test_three_queries_whatever_the_number_of_listings(self):
        # the listings, their windows, and that day's bookings grouped by listing and departure
        with self.assertNumQueries(3):
            bookable_on(BookableService.objects.all(), self.day)

    def test_it_agrees_with_the_booking_widget(self):
        for listing in BookableService.objects.all():
            offered = any(s['date'] == self.day for s in available_sessions(listing, days=7))
            with self.subTest(listing=listing.slug):
                self.assertEqual(offered, listing in bookable_on([listing], self.day))

    def test_nothing_in_nothing_out(self):
        self.assertEqual(bookable_on(BookableService.objects.none(), self.day), [])

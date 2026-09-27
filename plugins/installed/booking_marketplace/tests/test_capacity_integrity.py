"""Seat capacity must hold whatever departure string the client sends.

`daily_capacity` is per departure (models.BookableService), or for the whole day
when an experience runs with no fixed departure times. `create_booking` counted
only the bookings whose `time_slot` equals the submitted one, and validated the
submitted time only when the experience HAS fixed departures. So on a whole-day
experience each invented time ('10:00', '11:00', …) opened a fresh, empty seat
pool; and on a fixed-departure experience a booking with no time at all was
checked against the day, then ignored by every per-departure count after it.
"""

from __future__ import annotations

import contextlib
import datetime

from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.booking_marketplace import services as S
from plugins.installed.booking_marketplace.models import (
    AvailabilityWindow,
    BookableService,
    PricingTier,
)


def _svc(**kw):
    from plugins.installed.catalog.models import Vendor

    vendor = Vendor.objects.create(name='Cap Host', slug='cap-host', is_active=True)
    return BookableService.objects.create(
        vendor=vendor,
        name='Cap Tour',
        slug='cap-tour',
        price=Money(40, 'EUR'),
        daily_capacity=kw.get('daily_capacity', 4),
        max_guests_per_booking=kw.get('max_guests_per_booking', 10),
        is_active=True,
    )


def _target():
    return timezone.localdate() + datetime.timedelta(days=2)


def _try_book(svc, date, guests, time):
    with contextlib.suppress(S.BookingError):
        S.create_booking(
            svc, booking_date=date, guests=guests, name='G', email='g@example.com', time=time
        )


class DepartureCapacityTests(TestCase):
    def test_whole_day_capacity_cannot_be_split_by_invented_times(self):
        svc = _svc(daily_capacity=4)  # no availability windows: whole-day capacity
        target = _target()
        for time in ('', '10:00', '11:00'):
            _try_book(svc, target, 4, time)
        self.assertLessEqual(S.booked_guests(svc, target), 4)

    def test_a_booking_without_a_departure_cannot_overfill_one(self):
        svc = _svc(daily_capacity=4)
        target = _target()
        AvailabilityWindow.objects.create(
            service=svc, weekday=target.weekday(), start_time=datetime.time(9, 0)
        )
        for time in ('', '09:00'):
            _try_book(svc, target, 4, time)
        self.assertLessEqual(S.booked_guests(svc, target), 4)


class AvailableDatesTests(TestCase):
    def test_a_full_departure_does_not_hide_the_days_other_departures(self):
        svc = _svc(daily_capacity=5)
        target = _target()
        for hour in (9, 14):
            AvailabilityWindow.objects.create(
                service=svc, weekday=target.weekday(), start_time=datetime.time(hour, 0)
            )
        S.create_booking(
            svc, booking_date=target, guests=5, name='A', email='a@example.com', time='09:00'
        )

        dates = {d['date']: d['remaining'] for d in S.available_dates(svc, days=5)}
        # 14:00 still has all five seats, and the date picker is fed from here.
        self.assertIn(target, dates)
        self.assertEqual(dates[target], 5)


class PartySizeCapTests(TestCase):
    def test_per_booking_cap_applies_to_ticket_tiers(self):
        svc = _svc(daily_capacity=20, max_guests_per_booking=4)
        adult = PricingTier.objects.create(service=svc, name='Adult', price=Money(40, 'EUR'))
        child = PricingTier.objects.create(service=svc, name='Child', price=Money(20, 'EUR'))
        with self.assertRaises(S.BookingError):
            S.create_booking(
                svc,
                booking_date=_target(),
                name='Big party',
                email='party@example.com',
                tiers={str(adult.id): 3, str(child.id): 4},
            )

import datetime

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace import services as S
from plugins.installed.booking_marketplace.models import AvailabilityWindow, BookableService, Booking


def _svc():
    from plugins.installed.catalog.models import Vendor
    v = Vendor.objects.create(name='V', slug='v', is_active=True)
    return BookableService.objects.create(
        vendor=v, name='K', slug='k', price=Money(50, 'EUR'), daily_capacity=5,
    )


class SessionTests(TestCase):
    def test_two_departures_per_weekday(self):
        from django.utils import timezone
        svc = _svc()
        target = timezone.localdate() + datetime.timedelta(days=1)
        AvailabilityWindow.objects.create(service=svc, weekday=target.weekday(), start_time=datetime.time(9, 0))
        AvailabilityWindow.objects.create(service=svc, weekday=target.weekday(), start_time=datetime.time(14, 30))
        sessions = S.available_sessions(svc, days=3)
        day = next(s for s in sessions if s['date'] == target)
        self.assertEqual([t['time'] for t in day['times']], ['09:00', '14:30'])
        self.assertEqual(day['times'][0]['remaining'], 5)

    def test_capacity_per_departure(self):
        from django.utils import timezone
        svc = _svc()
        target = timezone.localdate() + datetime.timedelta(days=1)
        Booking.objects.create(
            service=svc, customer_name='A', customer_email='a@x.io',
            booking_date=target, time_slot='09:00', guests=2, status='confirmed',
        )
        self.assertEqual(S.booked_guests(svc, target, '09:00'), 2)
        self.assertEqual(S.booked_guests(svc, target, '14:30'), 0)
        self.assertEqual(S.booked_guests(svc, target), 2)  # date-level, back-compat

    def test_booking_rejects_unoffered_departure(self):
        from django.utils import timezone
        svc = _svc()
        target = timezone.localdate() + datetime.timedelta(days=1)
        AvailabilityWindow.objects.create(service=svc, weekday=target.weekday(), start_time=datetime.time(9, 0))
        # A real departure books fine…
        b = S.create_booking(svc, booking_date=target, guests=1, name='A', email='a@x.io', time='09:00')
        self.assertEqual(b.time_slot, '09:00')
        # …a slot that was never offered is rejected server-side.
        with self.assertRaises(S.BookingError):
            S.create_booking(svc, booking_date=target, guests=1, name='B', email='b@x.io', time='18:00')

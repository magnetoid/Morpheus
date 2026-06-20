"""Booking marketplace — models, slot logic, booking flow, disabled-by-default."""

import datetime
from decimal import Decimal

from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.booking_marketplace import views
from plugins.installed.booking_marketplace.models import (
    AvailabilityWindow,
    BookableService,
    Booking,
)
from plugins.installed.booking_marketplace.services import upcoming_slots


def _vendor():
    from plugins.installed.catalog.models import Vendor

    return Vendor.objects.create(name='Quill & Co', slug='quill-co', is_active=True)


def _service(vendor, **kw):
    svc = BookableService.objects.create(
        vendor=vendor,
        name=kw.get('name', 'Signing session'),
        slug=kw.get('slug', 'signing-session'),
        duration_minutes=kw.get('duration', 60),
        price=Money(Decimal('25.00'), 'USD'),
        is_active=True,
    )
    # Availability every weekday 09:00–17:00 so slots always exist in 14 days.
    for wd in range(7):
        AvailabilityWindow.objects.create(
            service=svc,
            weekday=wd,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(17, 0),
        )
    return svc


class ModelTests(TestCase):
    def test_create_chain(self):
        svc = _service(_vendor())
        self.assertEqual(svc.availability.count(), 7)
        self.assertEqual(svc.vendor.name, 'Quill & Co')


class SlotTests(TestCase):
    def test_generates_and_excludes_booked(self):
        svc = _service(_vendor())
        slots = upcoming_slots(svc)
        self.assertTrue(slots, 'expected upcoming slots from 09-17 daily availability')
        first = slots[0]
        # Booking the first slot removes it from the next computation.
        Booking.objects.create(
            service=svc,
            customer_name='A',
            customer_email='a@x.io',
            start_at=first,
            end_at=first + datetime.timedelta(minutes=60),
            status='pending',
            price=svc.price,
        )
        self.assertNotIn(first, upcoming_slots(svc))

    def test_no_availability_no_slots(self):
        v = _vendor()
        svc = BookableService.objects.create(
            vendor=v, name='X', slug='x', price=Money(Decimal('1'), 'USD')
        )
        self.assertEqual(upcoming_slots(svc), [])


class BookingFlowTests(TestCase):
    def _post(self, svc, data):
        req = RequestFactory().post(f'/bookings/{svc.slug}/', data)
        SessionMiddleware(lambda r: None).process_request(req)
        MessageMiddleware(lambda r: None).process_request(req)
        from django.contrib.auth.models import AnonymousUser

        req.user = AnonymousUser()
        return views.service_detail(req, svc.slug)

    def test_valid_booking_created(self):
        svc = _service(_vendor())
        slot = upcoming_slots(svc)[0]
        resp = self._post(svc, {'slot': slot.isoformat(), 'name': 'Jo', 'email': 'jo@x.io'})
        self.assertEqual(resp.status_code, 302)
        b = Booking.objects.get()
        self.assertEqual(b.customer_name, 'Jo')
        self.assertEqual(b.status, 'pending')
        self.assertEqual(b.end_at, slot + datetime.timedelta(minutes=60))

    def test_unavailable_slot_rejected(self):
        svc = _service(_vendor())
        past = (timezone.localtime() - datetime.timedelta(days=2)).isoformat()
        self._post(svc, {'slot': past, 'name': 'Jo', 'email': 'jo@x.io'})
        self.assertEqual(Booking.objects.count(), 0)

    def test_missing_fields_rejected(self):
        svc = _service(_vendor())
        slot = upcoming_slots(svc)[0]
        self._post(svc, {'slot': slot.isoformat(), 'name': '', 'email': ''})
        self.assertEqual(Booking.objects.count(), 0)


class DisabledByDefaultTests(TestCase):
    def test_plugin_ships_disabled(self):
        from plugins.installed.booking_marketplace.plugin import BookingMarketplacePlugin

        self.assertIs(BookingMarketplacePlugin.enabled_by_default, False)

    def test_base_default_is_enabled(self):
        from plugins.base import MorpheusPlugin

        self.assertIs(MorpheusPlugin.enabled_by_default, True)

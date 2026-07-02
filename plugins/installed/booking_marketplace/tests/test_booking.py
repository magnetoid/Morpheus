"""Booking marketplace — core flows: pricing, capacity, listing/marketplace, reviews, off-by-default."""

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import Client, RequestFactory, TestCase, override_settings
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.booking_marketplace import services as S
from plugins.installed.booking_marketplace import views
from plugins.installed.booking_marketplace.models import (
    AvailabilityWindow,
    BookableService,
    Booking,
    Enquiry,
)


def _vendor():
    from plugins.installed.catalog.models import Vendor

    return Vendor.objects.create(name='Acme Tours', slug='acme-tours', is_active=True)


def _service(vendor, **kw):
    return BookableService.objects.create(
        vendor=vendor,
        name=kw.get('name', 'City Kayak'),
        slug=kw.get('slug', 'city-kayak'),
        price=Money(Decimal('50.00'), 'EUR'),
        daily_capacity=kw.get('daily_capacity', 5),
        max_guests_per_booking=kw.get('max_guests', 10),
        is_active=True,
    )


def _future(days=2):
    return timezone.localdate() + datetime.timedelta(days=days)


class ModelTests(TestCase):
    def test_create_chain(self):
        svc = _service(_vendor())
        self.assertEqual(svc.vendor.name, 'Acme Tours')
        self.assertEqual(svc.price, Money(50, 'EUR'))
        self.assertEqual(svc.listing_kind, 'experience')


class PricingCapacityTests(TestCase):
    def test_totals_with_service_fee(self):
        b = S.create_booking(
            _service(_vendor()), booking_date=_future(), guests=3, name='Ana', email='a@x.io'
        )
        self.assertEqual(b.subtotal, Money(150, 'EUR'))
        self.assertEqual(b.service_fee, Money(18, 'EUR'))   # 12%
        self.assertEqual(b.total_price, Money(168, 'EUR'))
        self.assertEqual(b.status, 'confirmed')

    def test_capacity_guard_blocks_overbooking(self):
        svc = _service(_vendor(), daily_capacity=5)
        d = _future()
        S.create_booking(svc, booking_date=d, guests=3, name='A', email='a@x.io')
        with self.assertRaises(S.BookingError):
            S.create_booking(svc, booking_date=d, guests=3, name='B', email='b@x.io')

    def test_requires_approval_is_pending(self):
        svc = _service(_vendor())
        svc.requires_approval = True
        svc.save()
        b = S.create_booking(svc, booking_date=_future(), guests=1, name='A', email='a@x.io')
        self.assertEqual(b.status, 'pending')

    def test_past_date_rejected(self):
        with self.assertRaises(S.BookingError):
            S.create_booking(
                _service(_vendor()),
                booking_date=timezone.localdate() - datetime.timedelta(days=1),
                guests=1, name='A', email='a@x.io',
            )

    def test_weekday_restriction(self):
        svc = _service(_vendor())
        d = _future(1)
        AvailabilityWindow.objects.create(service=svc, weekday=(d.weekday() + 1) % 7)
        with self.assertRaises(S.BookingError):
            S.create_booking(svc, booking_date=d, guests=1, name='A', email='a@x.io')


def _post(svc, data):
    req = RequestFactory().post(f'/bookings/{svc.slug}/', data)
    SessionMiddleware(lambda r: None).process_request(req)
    MessageMiddleware(lambda r: None).process_request(req)
    req.user = AnonymousUser()
    return views.service_detail(req, svc.slug)


@override_settings(BOOKING_LISTING_MODE=False)
class MarketplaceFlowTests(TestCase):
    def test_valid_booking_created(self):
        svc = _service(_vendor())
        resp = _post(svc, {'booking_date': _future().isoformat(), 'guests': '2', 'name': 'Jo', 'email': 'jo@x.io'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Booking.objects.get().guests, 2)

    def test_missing_fields_rejected(self):
        svc = _service(_vendor())
        _post(svc, {'booking_date': _future().isoformat(), 'guests': '2', 'name': '', 'email': ''})
        self.assertEqual(Booking.objects.count(), 0)


@override_settings(BOOKING_LISTING_MODE=True)
class ListingFlowTests(TestCase):
    def test_enquiry_created_no_booking(self):
        svc = _service(_vendor())
        resp = _post(svc, {'name': 'Lead', 'email': 'lead@x.io', 'guests': '4', 'message': 'hi'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Enquiry.objects.count(), 1)
        self.assertEqual(Booking.objects.count(), 0)

    def test_enquiry_requires_email(self):
        svc = _service(_vendor())
        _post(svc, {'name': 'Lead', 'email': '', 'message': 'hi'})
        self.assertEqual(Enquiry.objects.count(), 0)


class ReviewTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.guest = U.objects.create(**{U.USERNAME_FIELD: 'guest@x.io'})
        self.stranger = U.objects.create(**{U.USERNAME_FIELD: 'stranger@x.io'})
        self.svc = _service(_vendor(), slug='rev-svc')
        Booking.objects.create(
            service=self.svc, customer=self.guest, customer_name='G',
            customer_email='g@x.io', booking_date=_future(), guests=1, status='confirmed',
        )

    def test_can_review_only_with_booking(self):
        self.assertTrue(S.can_review(self.svc, self.guest))
        self.assertFalse(S.can_review(self.svc, self.stranger))

    def test_create_review_is_gated(self):
        with self.assertRaises(S.BookingError):
            S.create_review(self.svc, user=self.stranger, rating=5)
        r = S.create_review(self.svc, user=self.guest, rating=5, title='Great', body='Loved it')
        self.assertEqual(r.rating, 5)


class DisabledByDefaultTests(TestCase):
    def test_plugin_ships_disabled(self):
        from plugins.installed.booking_marketplace.plugin import BookingMarketplacePlugin

        self.assertIs(BookingMarketplacePlugin.enabled_by_default, False)

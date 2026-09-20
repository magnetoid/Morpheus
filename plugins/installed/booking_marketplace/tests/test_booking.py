"""Booking marketplace — pricing, capacity, listing/marketplace flows, off-by-default."""

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import Http404
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
    Place,
)
from plugins.installed.booking_marketplace.tests._i18n import serbian_enabled
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin


def _vendor():
    from plugins.installed.catalog.models import Vendor

    return Vendor.objects.create(name='Adriatic Tours', slug='adriatic-tours', is_active=True)


def _service(vendor, **kw):
    return BookableService.objects.create(
        vendor=vendor,
        name=kw.get('name', 'Kotor Bay Kayak'),
        slug=kw.get('slug', 'kotor-kayak'),
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
        self.assertEqual(svc.vendor.name, 'Adriatic Tours')
        self.assertEqual(svc.price, Money(50, 'EUR'))


class PricingCapacityTests(TestCase):
    def test_totals_with_12pct_fee(self):
        b = S.create_booking(
            _service(_vendor()), booking_date=_future(), guests=3, name='Ana', email='a@x.io'
        )
        self.assertEqual(b.subtotal, Money(150, 'EUR'))
        self.assertEqual(b.service_fee, Money(18, 'EUR'))
        self.assertEqual(b.total_price, Money(168, 'EUR'))
        self.assertEqual(b.status, 'confirmed')

    def test_capacity_guard_blocks_overbooking(self):
        svc = _service(_vendor(), daily_capacity=5)
        d = _future()
        S.create_booking(svc, booking_date=d, guests=3, name='A', email='a@x.io')
        with self.assertRaises(S.BookingError):
            S.create_booking(svc, booking_date=d, guests=3, name='B', email='b@x.io')
        S.create_booking(svc, booking_date=d, guests=2, name='C', email='c@x.io')  # fills it
        self.assertEqual(S.booked_guests(svc, d), 5)

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
                guests=1,
                name='A',
                email='a@x.io',
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
@override_settings(BOOKING_PAYMENTS_READY=True)
class MarketplaceFlowTests(TestCase):
    """Marketplace mode WITH a payment step — the only state that may confirm.

    `BOOKING_PAYMENTS_READY` is required here because marketplace mode alone no
    longer confirms: a confirmed booking holds inventory, so it must not be
    created while nothing charges for it. See tests/test_no_free_booking.py.
    """

    def test_valid_booking_created(self):
        svc = _service(_vendor())
        resp = _post(
            svc,
            {
                'booking_date': _future().isoformat(),
                'guests': '2',
                'name': 'Jo',
                'email': 'jo@x.io',
            },
        )
        self.assertEqual(resp.status_code, 302)
        b = Booking.objects.get()
        self.assertEqual(b.guests, 2)
        self.assertEqual(b.status, 'confirmed')

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


class EarningsTests(TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Vendor

        U = get_user_model()
        self.user = U.objects.create(**{U.USERNAME_FIELD: 'earn@x.io'})
        self.vendor = Vendor.objects.create(
            name='Earn Co', slug='earn-co', is_active=True, owner=self.user
        )
        self.svc = _service(self.vendor, slug='earn-svc')  # €50/guest

    def test_earnings_summary(self):
        # 3 guests × €50 = €150 net, 12% fee = €18, gross €168.
        S.create_booking(self.svc, booking_date=_future(), guests=3, name='A', email='a@x.io')
        c = Client()
        c.force_login(self.user)
        resp = c.get('/bookings/host/earnings/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '150.00')  # net
        self.assertContains(resp, '18.00')  # platform fee
        self.assertContains(resp, '168.00')  # gross


class DisabledByDefaultTests(TestCase):
    def test_plugin_ships_disabled(self):
        from plugins.installed.booking_marketplace.app import BookingMarketplacePlugin

        self.assertIs(BookingMarketplacePlugin.enabled_by_default, False)


class ReviewTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.guest = U.objects.create(**{U.USERNAME_FIELD: 'guest@x.io'})
        self.stranger = U.objects.create(**{U.USERNAME_FIELD: 'stranger@x.io'})
        self.svc = _service(_vendor(), slug='rev-svc')
        Booking.objects.create(
            service=self.svc,
            customer=self.guest,
            customer_name='G',
            customer_email='g@x.io',
            booking_date=_future(),
            guests=1,
            status='confirmed',
        )

    def test_can_review_only_with_booking(self):
        self.assertTrue(S.can_review(self.svc, self.guest))
        self.assertFalse(S.can_review(self.svc, self.stranger))

    def test_create_review_is_gated(self):
        with self.assertRaises(S.BookingError):
            S.create_review(self.svc, user=self.stranger, rating=5)
        r = S.create_review(self.svc, user=self.guest, rating=5, title='Great', body='Loved it')
        self.assertEqual(r.rating, 5)
        self.assertEqual(self.svc.reviews.count(), 1)

    def test_one_review_per_user_updates(self):
        S.create_review(self.svc, user=self.guest, rating=4)
        S.create_review(self.svc, user=self.guest, rating=2)
        self.assertEqual(self.svc.reviews.count(), 1)
        self.assertEqual(self.svc.reviews.first().rating, 2)

    def test_rating_bounds(self):
        with self.assertRaises(S.BookingError):
            S.create_review(self.svc, user=self.guest, rating=9)

    def test_summary(self):
        S.create_review(self.svc, user=self.guest, rating=4)
        summary = S.review_summary(self.svc)
        self.assertEqual(summary['count'], 1)
        self.assertEqual(summary['avg'], 4.0)

    def test_create_review_resyncs_denormalised_rating(self):
        # A live review must move the storefront's denormalised fields the
        # same way seed_reviews does — not just the raw ServiceReview row.
        BookableService.objects.filter(pk=self.svc.pk).update(review_count=0, rating=0)
        review = S.create_review(self.svc, user=self.guest, rating=4)
        self.svc.refresh_from_db()
        self.assertEqual(self.svc.review_count, 1)
        self.assertEqual(float(self.svc.rating), float(review.rating))


@serbian_enabled
class I18nTests(MontenegroThemeMixin, TestCase):
    """Serbian is served at `/sr/…`, not by content negotiation.

    These asked for `/regions/` with `Accept-Language: sr` and asserted on
    Serbian copy. Django's LocaleMiddleware ignores Accept-Language on an
    unprefixed path whenever i18n_patterns are in use and the default language
    is unprefixed — `/regions/` IS the English URL — so they could only ever
    have rendered English, which is how they arrived from montenegro-new red.
    """

    def test_serbian_nav_translated(self):
        resp = Client().get('/sr/regions/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Doživljaji')  # "Experiences" → sr

    def test_english_default(self):
        resp = Client().get('/regions/', HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(resp, 'Experiences')
        self.assertNotContains(resp, 'Doživljaji')

    def test_serbian_list_heading(self):
        resp = Client().get('/sr/bookings/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Šta raditi u Crnoj Gori')


@override_settings(BOOKING_LISTING_MODE=False)
class ExperienceSearchTests(TestCase):
    def test_text_search_filters(self):
        v = _vendor()
        BookableService.objects.create(
            vendor=v,
            name='Kotor Kayak Trip',
            slug='k-kayak',
            price=Money(50, 'EUR'),
            is_active=True,
        )
        BookableService.objects.create(
            vendor=v, name='Budva Spa Day', slug='b-spa', price=Money(60, 'EUR'), is_active=True
        )
        body = Client().get('/bookings/?q=kayak').content.decode('utf-8')
        self.assertIn('Kotor Kayak Trip', body)
        self.assertNotIn('Budva Spa Day', body)


class PlacesTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        v = _vendor()
        self.place = Place.objects.create(
            name='Kotor',
            slug='kotor',
            region='kotor',
            summary='A fortified old town.',
            description='Bay town.',
            is_active=True,
        )
        BookableService.objects.create(
            vendor=v,
            name='Kotor Kayak X',
            slug='kotor-kayak-x',
            price=Money(50, 'EUR'),
            location='Kotor',
            region='kotor',
            is_active=True,
        )

    def test_places_index_lists_places(self):
        resp = Client().get('/places/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Kotor')

    def test_place_detail_lists_local_experiences(self):
        resp = Client().get('/places/kotor/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Kotor Kayak X')

    def test_unknown_place_404(self):
        self.assertEqual(Client().get('/places/narnia/').status_code, 404)

    @override_settings(BOOKING_LISTING_MODE=False)
    def test_homepage_features_places(self):
        resp = Client().get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'A fortified old town.')  # place summary in the strip


class RegionDirectoryTests(TestCase):
    def setUp(self):
        v = _vendor()
        BookableService.objects.create(
            vendor=v,
            name='Kotor A',
            slug='kotor-a',
            price=Money(10, 'EUR'),
            region='kotor',
            is_active=True,
        )
        BookableService.objects.create(
            vendor=v,
            name='Budva B',
            slug='budva-b',
            price=Money(10, 'EUR'),
            region='budva',
            is_active=True,
        )

    def test_regions_index_lists_regions(self):
        resp = Client().get('/regions/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Kotor Bay')

    def test_region_detail_filters_by_region(self):
        resp = Client().get('/regions/kotor/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Kotor A')
        self.assertNotContains(resp, 'Budva B')

    def test_unknown_region_404(self):
        self.assertEqual(Client().get('/regions/narnia/').status_code, 404)


@override_settings(BOOKING_LISTING_MODE=False)
@serbian_enabled
class RichExperienceTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        from decimal import Decimal

        self.svc = BookableService.objects.create(
            vendor=_vendor(),
            name='Rich Kayak',
            slug='rich-kayak',
            price=Money(65, 'EUR'),
            original_price=Money(85, 'EUR'),
            is_bestseller=True,
            rating=Decimal('4.9'),
            review_count=234,
            location='Kotor',
            duration_label='4 hours',
            highlights=['Hidden caves', 'Local guide'],
            included=['Kayak', 'Life jacket'],
            not_included=['Hotel pickup'],
            is_active=True,
        )

    def test_card_shows_rich_fields(self):
        body = Client().get('/bookings/').content.decode('utf-8')
        # The badge's copy is the theme's to choose (it reads 'Guest favourite'
        # today); assert the marker, not a display word.
        self.assertIn('data-badge="bestseller"', body)
        self.assertIn('Rich Kayak', body)
        self.assertIn('85', body)  # was-price strikethrough

    def test_detail_shows_highlights_and_included(self):
        body = Client().get('/bookings/rich-kayak/').content.decode('utf-8')
        self.assertIn('Highlights', body)
        self.assertIn('Hidden caves', body)
        self.assertIn("What's included", body)
        self.assertIn('234 reviews', body)

    def test_detail_serbian_labels(self):
        body = Client().get('/sr/bookings/rich-kayak/').content.decode('utf-8')
        self.assertIn('Istaknuto', body)  # Highlights → sr
        self.assertIn('Domaćin', body)  # Hosted by → sr


class HomepageExperiencesTests(MontenegroThemeMixin, TestCase):
    def test_featured_experiences_tag_orders_bestsellers_first(self):
        from decimal import Decimal

        from plugins.installed.booking_marketplace.templatetags.booking_tags import (
            featured_experiences,
        )

        v = _vendor()
        BookableService.objects.create(
            vendor=v,
            name='Feat A',
            slug='feat-a',
            price=Money(40, 'EUR'),
            is_active=True,
            is_bestseller=True,
            rating=Decimal('4.9'),
        )
        BookableService.objects.create(
            vendor=v,
            name='Feat B',
            slug='feat-b',
            price=Money(30, 'EUR'),
            is_active=True,
            is_bestseller=False,
            rating=Decimal('4.0'),
        )
        out = featured_experiences(8)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0].slug, 'feat-a')  # bestseller first

    @override_settings(BOOKING_LISTING_MODE=False)
    def test_homepage_renders_experiences(self):
        BookableService.objects.create(
            vendor=_vendor(),
            name='Home Feat Exp',
            slug='home-feat',
            price=Money(40, 'EUR'),
            is_active=True,
        )
        resp = Client().get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Home Feat Exp')


class HostUITests(TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Vendor

        U = get_user_model()
        self.user = U.objects.create(**{U.USERNAME_FIELD: 'host@x.io'})
        self.other = U.objects.create(**{U.USERNAME_FIELD: 'other@x.io'})
        self.vendor = Vendor.objects.create(
            name='Adriatic Tours', slug='adriatic-tours', is_active=True, owner=self.user
        )

    def _req(self, method, path, data=None, user=None):
        req = getattr(RequestFactory(), method)(path, data or {})
        SessionMiddleware(lambda r: None).process_request(req)
        MessageMiddleware(lambda r: None).process_request(req)
        req.user = user
        return req

    def test_non_host_sees_prompt(self):
        from plugins.installed.booking_marketplace import host

        resp = host.host_services(self._req('get', '/bookings/host/', user=self.other))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Become a host', resp.content)

    def test_create_service_with_availability(self):
        from plugins.installed.booking_marketplace import host

        data = {
            'name': 'Bay Sunset Sail',
            'price': '80',
            'duration_minutes': '180',
            'daily_capacity': '8',
            'max_guests_per_booking': '6',
            'region': 'kotor',
            'weekdays': ['5', '6'],
            'is_active': 'on',
            'short_description': 'x',
            'description': 'y',
        }
        resp = host.host_service_form(
            self._req('post', '/bookings/host/new/', data, user=self.user)
        )
        self.assertEqual(resp.status_code, 302)
        svc = BookableService.objects.get(name='Bay Sunset Sail')
        self.assertEqual(svc.vendor, self.vendor)
        self.assertEqual(svc.price, Money(80, 'EUR'))
        self.assertEqual(svc.region, 'kotor')
        self.assertEqual(svc.availability.count(), 2)

    def test_cannot_edit_other_hosts_service(self):
        from plugins.installed.booking_marketplace import host
        from plugins.installed.catalog.models import Vendor

        v2 = Vendor.objects.create(name='Other', slug='other-co', is_active=True, owner=self.other)
        BookableService.objects.create(
            vendor=v2, name='Theirs', slug='theirs', price=Money(10, 'EUR')
        )
        with self.assertRaises(Http404):
            host.host_service_form(
                self._req('get', '/bookings/host/theirs/edit/', user=self.user), slug='theirs'
            )

    def test_booking_action_confirm(self):
        from plugins.installed.booking_marketplace import host

        svc = BookableService.objects.create(
            vendor=self.vendor, name='S', slug='s', price=Money(20, 'EUR'), daily_capacity=5
        )
        b = Booking.objects.create(
            service=svc,
            customer_name='A',
            customer_email='a@x.io',
            booking_date=_future(),
            guests=1,
            status='pending',
        )
        resp = host.host_bookings(
            self._req(
                'post',
                '/bookings/host/bookings/',
                {'booking_id': str(b.id), 'action': 'confirm'},
                user=self.user,
            )
        )
        self.assertEqual(resp.status_code, 302)
        b.refresh_from_db()
        self.assertEqual(b.status, 'confirmed')

"""Storefront smoke tests for the stays engine."""

import datetime
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin


def _future(days):
    return (timezone.localdate() + datetime.timedelta(days=days)).isoformat()


class StayViewTests(TestCase):
    def setUp(self):
        from plugins.installed.booking_marketplace.models import Property, RoomType
        from plugins.installed.catalog.models import Vendor

        v = Vendor.objects.create(name='Adriatic', slug='adriatic')
        self.prop = Property.objects.create(
            vendor=v,
            name='Hotel Kotor Bay',
            slug='hotel-kotor-bay',
            property_type='hotel',
            star_rating=4,
            region='kotor',
            location='Kotor',
            amenities=['pool', 'spa'],
            price_from=Money(Decimal('120'), 'EUR'),
            is_active=True,
        )
        self.room = RoomType.objects.create(
            property=self.prop,
            name='Deluxe Double',
            slug='deluxe-double',
            base_rate=Money(Decimal('120'), 'EUR'),
            max_occupancy=3,
            max_adults=2,
            max_children=1,
            room_count=4,
        )

    def test_index_lists_property(self):
        resp = self.client.get(reverse('booking_marketplace:stays'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Hotel Kotor Bay')

    def test_index_provides_a_meta_description(self):
        """The /hotels/ hub had 1,700+ words but no meta description (SEO audit
        2026-09) — stay_detail set one, stays_index didn't. It must supply one
        (via the same `seo_description` context the shared head reads), kept to a
        SERP-friendly length."""
        resp = self.client.get(reverse('booking_marketplace:stays'))
        desc = str(resp.context['seo_description'])
        self.assertTrue(desc.strip(), 'the hotels hub must have a meta description')
        self.assertLessEqual(len(desc), 160, f'hub meta description too long: {len(desc)}')

    def test_detail_renders_room_types(self):
        resp = self.client.get(reverse('booking_marketplace:stay_detail', args=['hotel-kotor-bay']))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Deluxe Double')

    def test_quote_endpoint_returns_totals(self):
        url = reverse('booking_marketplace:stay_quote', args=['hotel-kotor-bay'])
        resp = self.client.get(
            url,
            {
                'room_type': str(self.room.id),
                'check_in': _future(10),
                'check_out': _future(13),
                'rooms': 1,
                'adults': 2,
                'children': 1,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['total'], '412.20')
        self.assertEqual(data['available'], 4)

    @override_settings(BOOKING_LISTING_MODE=False, BOOKING_PAYMENTS_READY=True)
    def test_book_creates_booking_only_once_payments_are_ready(self):
        """Marketplace mode alone is no longer enough to confirm a booking.

        This test used to assert that marketplace mode by itself created a
        StayBooking. That was the bug: confirmation held real inventory while
        nothing charged for it. Confirming now additionally requires
        BOOKING_PAYMENTS_READY.
        """
        from plugins.installed.booking_marketplace.models import StayBooking

        url = reverse('booking_marketplace:stay_book', args=['hotel-kotor-bay'])
        resp = self.client.post(
            url,
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
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(StayBooking.objects.count(), 1)

    @override_settings(BOOKING_LISTING_MODE=True)
    @patch('plugins.installed.booking_marketplace.stay_views.listing_mode', return_value=True)
    def test_book_creates_enquiry_in_listing_mode(self, _m):
        from plugins.installed.booking_marketplace.models import StayBooking, StayEnquiry

        url = reverse('booking_marketplace:stay_book', args=['hotel-kotor-bay'])
        resp = self.client.post(
            url,
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
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(StayEnquiry.objects.count(), 1)
        self.assertEqual(StayBooking.objects.count(), 0)


class StayThemeTemplateTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        from plugins.installed.booking_marketplace.models import Property, RoomType
        from plugins.installed.catalog.models import Vendor

        v = Vendor.objects.create(name='Adriatic', slug='adriatic-theme')
        self.prop = Property.objects.create(
            vendor=v,
            name='Hotel Kotor Bay',
            slug='hotel-kotor-bay-theme',
            property_type='hotel',
            star_rating=4,
            region='kotor',
            location='Kotor',
            amenities=['pool', 'spa'],
            price_from=Money(Decimal('120'), 'EUR'),
            latitude=Decimal('42.424200'),
            longitude=Decimal('18.771200'),
        )
        RoomType.objects.create(
            property=self.prop,
            name='Deluxe Double',
            slug='deluxe-double',
            base_rate=Money(Decimal('120'), 'EUR'),
            max_occupancy=3,
            max_adults=2,
            max_children=1,
            room_count=4,
            bed_configuration='1 King',
        )

    def test_detail_has_booking_form_and_amenities(self):
        resp = self.client.get(
            reverse('booking_marketplace:stay_detail', args=['hotel-kotor-bay-theme'])
        )
        self.assertContains(resp, 'Deluxe Double')
        self.assertContains(resp, 'Swimming pool')  # amenity label from AMENITY_LABELS
        self.assertContains(resp, 'name="check_in"')  # date-range form
        self.assertContains(resp, 'data-quote-url')  # live-quote JS hook (theme-only)

    @override_settings(BOOKING_LISTING_MODE=True)
    @patch('plugins.installed.booking_marketplace.stay_views.listing_mode', return_value=True)
    def test_detail_hides_price_and_shows_enquiry_in_listing_mode(self, _m):
        resp = self.client.get(
            reverse('booking_marketplace:stay_detail', args=['hotel-kotor-bay-theme'])
        )
        self.assertContains(resp, 'Contact for price')
        self.assertNotContains(resp, 'Book now')  # marketplace CTA hidden
        self.assertNotContains(resp, '/ night')  # nightly price row hidden

    def test_nav_has_hotels_link(self):
        resp = self.client.get(reverse('booking_marketplace:stays'))
        self.assertContains(resp, 'href="/hotels/"')

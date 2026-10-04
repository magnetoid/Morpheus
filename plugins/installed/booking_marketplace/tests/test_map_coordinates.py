"""Map coordinates must not be localized.

The Montenegro theme hands Leaflet the coordinates through ``data-lat``/``data-lng``
and reads them back with unary plus. Django localizes a Decimal in a Serbian
request to ``42,420000``, which ``+`` turns into NaN, and Leaflet threw
``Invalid LatLng object: (NaN, NaN)`` on every ``/sr/`` place, experience and stay
page while the English pages worked.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.booking_marketplace.tests._i18n import serbian_enabled
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin


def _vendor():
    from plugins.installed.catalog.models import Vendor

    return Vendor.objects.create(name='Makers', slug='makers', is_active=True)


@serbian_enabled
@override_settings(BOOKING_LISTING_MODE=False)
class MapCoordinateTests(MontenegroThemeMixin, TestCase):
    def assert_dot_decimal(self, body: str):
        self.assertIn('data-lat="42.42', body)
        self.assertIn('data-lng="18.77', body)
        self.assertNotIn('data-lat="42,', body)
        self.assertNotIn('data-lng="18,', body)

    def test_place_page_in_serbian(self):
        from plugins.installed.booking_marketplace.models import Place

        Place.objects.create(
            name='Testville',
            slug='testville',
            region='kotor',
            summary='A test town on the bay.',
            latitude=Decimal('42.42'),
            longitude=Decimal('18.77'),
        )
        response = self.client.get('/sr/places/testville/')
        self.assertEqual(response.status_code, 200)
        self.assert_dot_decimal(response.content.decode())

    def test_experience_page_in_serbian(self):
        from plugins.installed.booking_marketplace.models import BookableService

        BookableService.objects.create(
            vendor=_vendor(),
            name='Bay Kayak',
            slug='bay-kayak',
            price=Money(50, 'EUR'),
            listing_kind='experience',
            latitude=Decimal('42.42'),
            longitude=Decimal('18.77'),
        )
        response = self.client.get('/sr/bookings/bay-kayak/')
        self.assertEqual(response.status_code, 200)
        self.assert_dot_decimal(response.content.decode())

    def test_stay_page_in_serbian(self):
        from plugins.installed.booking_marketplace.models import Property

        Property.objects.create(
            vendor=_vendor(),
            name='Hotel Kotor Bay',
            slug='hotel-kotor-bay',
            property_type='hotel',
            region='kotor',
            location='Kotor',
            latitude=Decimal('42.42'),
            longitude=Decimal('18.77'),
        )
        response = self.client.get('/sr/hotels/hotel-kotor-bay/')
        self.assertEqual(response.status_code, 200)
        self.assert_dot_decimal(response.content.decode())

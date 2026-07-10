"""listing_kind discriminator + logistics fields on BookableService."""

from decimal import Decimal

from django.test import Client, TestCase, override_settings
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService


def _vendor():
    from plugins.installed.catalog.models import Vendor

    return Vendor.objects.create(name='Makers', slug='makers', is_active=True)


class ListingKindTests(TestCase):
    def test_defaults_to_experience(self):
        svc = BookableService.objects.create(
            vendor=_vendor(),
            name='Kayak',
            slug='kayak',
            price=Money(50, 'EUR'),
        )
        self.assertEqual(svc.listing_kind, 'experience')

    def test_product_kind_with_logistics(self):
        svc = BookableService.objects.create(
            vendor=_vendor(),
            name='Vranac',
            slug='vranac',
            price=Money(18, 'EUR'),
            listing_kind='product',
            latitude=Decimal('42.4247'),
            longitude=Decimal('18.7712'),
            languages=['English'],
            what_to_bring=['ID'],
            itinerary=[{'title': 'Meet', 'detail': 'At the pier'}],
        )
        svc.refresh_from_db()
        self.assertEqual(svc.listing_kind, 'product')
        self.assertEqual(svc.languages, ['English'])
        self.assertEqual(svc.itinerary[0]['title'], 'Meet')


@override_settings(BOOKING_LISTING_MODE=False)
class BrowseSplitTests(TestCase):
    def setUp(self):
        v = _vendor()
        BookableService.objects.create(
            vendor=v,
            name='Kayak Trip',
            slug='kayak-trip',
            price=Money(50, 'EUR'),
            listing_kind='experience',
            is_active=True,
        )
        BookableService.objects.create(
            vendor=v,
            name='Vranac Red',
            slug='vranac-red',
            price=Money(18, 'EUR'),
            listing_kind='product',
            is_active=True,
        )

    def test_bookings_shows_only_experiences(self):
        body = Client().get('/bookings/').content.decode('utf-8')
        self.assertIn('Kayak Trip', body)
        self.assertNotIn('Vranac Red', body)

    def test_shop_shows_only_products(self):
        body = Client().get('/shop/').content.decode('utf-8')
        self.assertIn('Vranac Red', body)
        self.assertNotIn('Kayak Trip', body)

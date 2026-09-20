"""Detail page branches on listing_kind and renders rich content."""

from decimal import Decimal

from django.test import Client, TestCase, override_settings
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import AddOn, BookableService, PricingTier
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin


def _vendor():
    from plugins.installed.catalog.models import Vendor

    return Vendor.objects.create(name='Makers', slug='makers', is_active=True)


@override_settings(BOOKING_LISTING_MODE=False)
class DetailKindTests(MontenegroThemeMixin, TestCase):
    def test_experience_shows_itinerary_and_map(self):
        BookableService.objects.create(
            vendor=_vendor(),
            name='Bay Kayak',
            slug='bay-kayak',
            price=Money(50, 'EUR'),
            listing_kind='experience',
            latitude=Decimal('42.42'),
            longitude=Decimal('18.77'),
            itinerary=[{'title': 'Depart', 'detail': 'From the old pier'}],
            what_to_bring=['Swimwear'],
            is_active=True,
        )
        body = Client().get('/bookings/bay-kayak/').content.decode('utf-8')
        self.assertIn('Itinerary', body)
        self.assertIn('From the old pier', body)
        self.assertIn('What to bring', body)
        self.assertIn('leaflet', body.lower())  # map assets loaded

    def test_product_hides_itinerary_shows_quantity(self):
        BookableService.objects.create(
            vendor=_vendor(),
            name='Vranac Red',
            slug='vranac-red',
            price=Money(18, 'EUR'),
            listing_kind='product',
            is_active=True,
        )
        body = Client().get('/bookings/vranac-red/').content.decode('utf-8')
        self.assertNotIn('Itinerary', body)
        self.assertNotIn('leaflet', body.lower())  # no map for products
        self.assertIn('name="guests"', body)  # quantity/enquiry widget still present


@override_settings(BOOKING_LISTING_MODE=False)
class WidgetTests(MontenegroThemeMixin, TestCase):
    def test_tier_and_addon_inputs_rendered(self):
        svc = BookableService.objects.create(
            vendor=_vendor(),
            name='Kayak',
            slug='kayak',
            price=Money(50, 'EUR'),
            listing_kind='experience',
            is_active=True,
        )
        adult = PricingTier.objects.create(service=svc, name='Adult', price=Money(50, 'EUR'))
        pickup = AddOn.objects.create(service=svc, name='Pickup', price=Money(10, 'EUR'))
        body = Client().get('/bookings/kayak/').content.decode('utf-8')
        self.assertIn(f'tier_{adult.id}', body)
        self.assertIn(f'addon_{pickup.id}', body)
        self.assertIn('Adult', body)
        self.assertIn('Pickup', body)

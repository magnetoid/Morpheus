"""An experience links the destination guides of its region."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService, Place
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Vendor


class ExperienceNearbyPlacesTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        self.svc = BookableService.objects.create(
            vendor=vendor,
            name='Kayak the bay',
            slug='kayak-the-bay',
            listing_kind='experience',
            region='kotor',
            location='Kotor',
            price=Money(Decimal('50'), 'EUR'),
            is_active=True,
        )
        Place.objects.create(
            name='Perast', slug='perast', region='kotor', summary='A baroque town.'
        )
        Place.objects.create(name='Žabljak', slug='zabljak', region='durmitor')

    def _page(self):
        return self.client.get(f'/bookings/{self.svc.slug}/').content.decode()

    def test_places_in_the_same_region_are_linked(self):
        html = self._page()
        section = html[html.index('id="places-nearby"') :]
        self.assertIn('href="/places/perast/"', section)
        self.assertNotIn('href="/places/zabljak/"', section)

    def test_a_product_listing_links_no_places(self):
        BookableService.objects.filter(pk=self.svc.pk).update(listing_kind='product')
        self.assertNotIn('id="places-nearby"', self._page())

"""The booking page's head comes from its Product, as the product editor shows it.

The page passed the listing as its SEO object, so the product editor's SEO panel
(title, description) changed nothing on the page, and the page's title differed
from the one the editor previewed.
"""

from __future__ import annotations

import re
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.products import ensure_product
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Product, Vendor


class ListingSeoFromProductTests(TestCase):
    def setUp(self):
        vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        self.svc = BookableService.objects.create(
            vendor=vendor,
            name='Kayak the bay',
            slug='kayak-the-bay',
            listing_kind='experience',
            location='Kotor',
            price=Money(Decimal('50'), 'EUR'),
            is_active=True,
            short_description='Paddle the bay at dawn.',
            description='Paddle the bay.',
        )
        self.product = ensure_product(self.svc)

    def _seo(self, **fields):
        from plugins.installed.seo.models import SeoMeta

        SeoMeta.objects.update_or_create(
            content_type=ContentType.objects.get_for_model(Product),
            object_id=str(self.product.pk),
            defaults={'auto_filled': False, **fields},
        )

    def _head(self):
        html = self.client.get(f'/bookings/{self.svc.slug}/').content.decode()

        def tag(pattern):
            match = re.search(pattern, html, re.S)
            return match.group(1).strip() if match else None

        return {
            'title': tag(r'<title>(.*?)</title>'),
            'og_title': tag(r'property="og:title" content="([^"]*)"'),
            'description': tag(r'name="description" content="([^"]*)"'),
        }

    def test_the_products_seo_title_is_the_page_title(self):
        self._seo(title='Sunrise Kayak in the Bay of Kotor')
        head = self._head()
        self.assertTrue(head['title'].startswith('Sunrise Kayak in the Bay of Kotor'), head)
        self.assertEqual(head['og_title'], 'Sunrise Kayak in the Bay of Kotor')

    def test_the_products_seo_description_is_the_page_description(self):
        self._seo(description='Two calm hours on the water before the cruise ships arrive.')
        self.assertEqual(
            self._head()['description'],
            'Two calm hours on the water before the cruise ships arrive.',
        )


class MontenegroListingSeoFromProductTests(MontenegroThemeMixin, ListingSeoFromProductTests):
    """The Montenegro theme renders the booking page; its head must follow the product too."""

"""A service product (an experience an app books) is a product, but not a shop good.

Montenegro's experiences become catalog Products extended by booking_marketplace
(docs/plans/booking-extends-product-2026-10.md). The dashboard, Linda and web stories
see them; the shopping surfaces (catalogue, sitemap, channel feeds) list only
Product.objects.shoppable().
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product


class ServiceProductTests(TestCase):
    def test_shoppable_leaves_out_services_and_inactive(self):
        Product.objects.create(
            name='Book', slug='book', sku='B1', status='active', price=Money(Decimal('10'), 'EUR')
        )
        Product.objects.create(
            name='Kayak',
            slug='kayak',
            sku='S1',
            status='active',
            product_type='service',
            price=Money(Decimal('50'), 'EUR'),
        )
        Product.objects.create(
            name='Old', slug='old', sku='O1', status='archived', price=Money(Decimal('5'), 'EUR')
        )
        self.assertEqual(list(Product.objects.shoppable().values_list('slug', flat=True)), ['book'])

    def test_service_is_a_product_type(self):
        self.assertIn('service', dict(Product.PRODUCT_TYPES))

    def test_money_lookups_match_the_currency_on_the_custom_manager(self):
        # django-money's manager turns price=Money(10, 'EUR') into amount AND currency;
        # a plain manager would match both products on the amount alone.
        Product.objects.create(
            name='Book', slug='book', sku='B1', status='active', price=Money(Decimal('10'), 'EUR')
        )
        Product.objects.create(
            name='Pen', slug='pen', sku='P1', status='active', price=Money(Decimal('10'), 'USD')
        )
        self.assertEqual(Product.objects.filter(price=Money(Decimal('10'), 'EUR')).count(), 1)
        self.assertEqual(
            Product.objects.shoppable().filter(price=Money(Decimal('10'), 'EUR')).count(), 1
        )

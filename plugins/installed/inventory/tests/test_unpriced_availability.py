"""An unpriced product is not in stock.

The cart refuses a product priced at 0 (``orders.CartService.add_item``), so
the availability the product page, its JSON-LD and the channel feeds read must
not claim otherwise — a $0 in-stock offer is also a Merchant Center violation.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.inventory.services import product_availability


def _product(slug, price):
    return Product.objects.create(
        name=slug, slug=slug, sku=slug.upper(), price=Money(Decimal(price), 'USD'), status='active'
    )


class UnpricedAvailabilityTests(TestCase):
    def test_an_unpriced_product_is_out_of_stock(self):
        self.assertEqual(product_availability(_product('free-oil', '0')), 'out_of_stock')

    def test_a_priced_product_is_unaffected(self):
        self.assertEqual(product_availability(_product('rose-oil', '12.50')), 'in_stock')

    def test_a_product_loaded_without_its_price_is_read_safely(self):
        # Product pages load rows with .only(); touching a deferred djmoney
        # field raises KeyError, which must not turn into a wrong answer.
        pk = _product('free-oil', '0').pk
        deferred = Product.objects.only('id', 'status').get(pk=pk)
        self.assertEqual(product_availability(deferred), 'out_of_stock')

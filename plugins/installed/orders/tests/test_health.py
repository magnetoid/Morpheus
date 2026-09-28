"""Orders' health check prices a real cart and leaves nothing behind."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.health import cart_pricing_check
from plugins.installed.orders.models import Cart


class CartPricingCheckTests(TestCase):
    def test_a_priced_product_prices_and_the_cart_is_rolled_back(self):
        Product.objects.create(
            name='Health Book', slug='health-book', sku='H-1',
            price=Money(Decimal('12.00'), 'USD'), status='active',
        )  # fmt: skip
        result = cart_pricing_check()
        self.assertTrue(result['ok'], result)
        self.assertFalse(Cart.objects.filter(session_key='health-check').exists())

    def test_a_store_without_priced_products_is_not_a_failure(self):
        self.assertTrue(cart_pricing_check()['ok'])

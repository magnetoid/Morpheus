"""A product nobody has priced yet cannot be bought.

Eighteen active products on a live store had a price of 0 and could be added
to the cart and ordered for nothing. ``CartService.add_item`` is the one place
every add goes through (storefront, API, agents), so it refuses them there.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Cart
from plugins.installed.orders.services import CartService


def _product(slug, price):
    return Product.objects.create(
        name=slug, slug=slug, sku=slug.upper(), price=Money(Decimal(price), 'USD'), status='active'
    )


class UnpricedProductCartTests(TestCase):
    def test_the_cart_refuses_an_unpriced_product(self):
        cart = Cart.objects.create(session_key='unpriced')
        with self.assertRaisesMessage(ValueError, 'not available to buy yet'):
            CartService.add_item(cart=cart, product_id=_product('free-oil', '0').pk)
        self.assertFalse(cart.items.exists())

    def test_a_priced_product_still_adds(self):
        cart = Cart.objects.create(session_key='priced')
        CartService.add_item(cart=cart, product_id=_product('rose-oil', '12.50').pk)
        self.assertEqual(cart.items.count(), 1)

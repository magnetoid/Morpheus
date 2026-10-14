"""A service product (a booking listing) is booked on its own page, never bought from a cart.

Every cart door — the storefront form, GraphQL, the MCP cart tools, agentic checkout,
wishlists — goes through CartService.add_item, so the refusal lives there.
"""

import uuid
from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.health import cart_pricing_check
from plugins.installed.orders.models import Cart
from plugins.installed.orders.services import CartService


class ServiceProductCartTests(TestCase):
    def _product(self, sku, product_type, pk=None):
        return Product.objects.create(
            id=pk or uuid.uuid4(),
            name=sku,
            slug=sku.lower(),
            sku=sku,
            status='active',
            product_type=product_type,
            price=Money(Decimal('50'), 'USD'),
        )

    def test_a_service_product_cannot_be_added_to_a_cart(self):
        tour = self._product('TOUR', 'service')
        cart = Cart.objects.create(session_key='s1')
        with self.assertRaisesMessage(ValueError, 'booked on its own page'):
            CartService.add_item(cart, str(tour.id))
        self.assertEqual(cart.items.count(), 0)

    def test_the_nightly_cart_check_prices_a_shoppable_product(self):
        self._product('TOUR', 'service', pk=uuid.UUID(int=1))  # first in the check's pk order
        self._product('MUG', 'simple', pk=uuid.UUID(int=2))
        result = cart_pricing_check()
        self.assertTrue(result['ok'], result)

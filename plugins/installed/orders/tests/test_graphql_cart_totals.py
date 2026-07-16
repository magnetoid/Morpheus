"""cartTotals regression (prod incident 2026-07-16): the resolver called its
sibling through ``self`` — but strawberry invokes root Query resolvers with
``self`` = root_value (None), so every cartTotals call crashed with
"'NoneType' object has no attribute 'cart'" and the checkout JS's totals
refresh errored. Executed here through the REAL composed schema with the
same root_value production uses."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.test import RequestFactory, TestCase
from djmoney.money import Money

from api.client import internal_graphql
from plugins.installed.catalog.models import Product
from plugins.installed.orders.services import CartService

_QUERY = """
query CartTotals($cartId: ID!) {
  cartTotals(cartId: $cartId) {
    subtotal { amount currency }
    total { amount currency }
  }
}
"""


class CartTotalsSchemaTests(TestCase):
    def test_cart_totals_executes_with_none_root_value(self):
        product = Product.objects.create(
            name='Totals Book',
            slug='totals-book',
            sku='TOT-1',
            price=Money(Decimal('15.00'), 'USD'),
            status='active',
        )
        cart = CartService.get_or_create_cart(session_key='s-totals')
        CartService.add_item(cart, str(product.id), quantity=2)

        request = RequestFactory().post('/graphql/')
        request.session = self.client.session  # anonymous session, no cart claim
        # Session-key scoping: an anonymous cart with a session_key only reads
        # for that session — attach the owning key so the lookup authorizes.
        request.session = type(
            'S', (), {'session_key': 's-totals', 'get': staticmethod(lambda *a, **k: None)}
        )()

        data = internal_graphql(_QUERY, {'cartId': str(cart.id)}, request=request)
        totals = data['cartTotals']
        self.assertIsNotNone(totals, 'cartTotals returned null for a real cart')
        self.assertEqual(Decimal(str(totals['subtotal']['amount'])), Decimal('30.00'))

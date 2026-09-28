"""A tree-planting offset shows up everywhere the order's total does.

The offset was added to the total and to nothing else, so the order email and
the dashboard listed a subtotal, shipping and tax that fell $1.50 short of the
total. The breakdown now names the charge, the order keeps it, and the order
email lists it (plus the discount line it never had).
"""

from __future__ import annotations

from decimal import Decimal

from django.template.loader import render_to_string
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Cart, CartItem
from plugins.installed.orders.services import OrderService


class OrderExtrasTests(TestCase):
    def setUp(self):
        product = Product.objects.create(
            name='Offset Book',
            slug='offset-book',
            sku='ECO-1',
            price=Money(Decimal('8.00'), 'USD'),
            status='active',
        )
        self.cart = Cart.objects.create(session_key='eco', metadata={'eco_impact_optin': True})
        CartItem.objects.create(
            cart=self.cart, product=product, quantity=1, unit_price=Money(Decimal('8.00'), 'USD')
        )

    def _order(self):
        address = {'country': 'US'}
        return OrderService.create_from_cart(self.cart, 'shopper@example.com', address, address)

    def test_the_offset_is_a_named_line_on_the_order(self):
        lines = [(e['label'], e['amount'].amount) for e in self._order().extra_lines]
        self.assertEqual(lines, [('Plant a tree', Decimal('1.50'))])

    def test_the_order_lines_add_up_to_the_total(self):
        order = self._order()
        lines = (
            order.subtotal.amount
            + order.shipping_total.amount
            + order.tax_total.amount
            - order.discount_total.amount
            + sum(e['amount'].amount for e in order.extra_lines)
        )
        self.assertEqual(lines, order.total.amount)
        self.assertEqual(order.total.amount, Decimal('9.50'))

    def test_the_order_email_lists_the_offset(self):
        body = render_to_string('emails/order_placed.txt', {'order': self._order()})
        self.assertIn('Plant a tree: $1.50', body)

"""An order keeps the rates behind its tax, so its invoice can itemise them.

The order stored one ``tax_total`` and nothing else, so an invoice could only
print "Tax" — never "VAT 20%" — however many rates checkout had applied. The tax
handler now names its lines in the breakdown, the order keeps them, and
``Order.tax_lines`` shows them only while they add up to the total.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Cart, CartItem, Order
from plugins.installed.orders.services import OrderService
from plugins.installed.tax.models import TaxRate, TaxRegion


class TaxLinesOnOrderTests(TestCase):
    def setUp(self):
        product = Product.objects.create(
            name='Taxed Lamp',
            slug='taxed-lamp',
            sku='TAX-LAMP',
            price=Money(Decimal('10.00'), 'EUR'),
            status='active',
        )
        self.cart = Cart.objects.create(session_key='tax-lines')
        CartItem.objects.create(
            cart=self.cart, product=product, quantity=2, unit_price=Money(Decimal('10.00'), 'EUR')
        )
        region = TaxRegion.objects.create(name='Germany', country='DE')
        TaxRate.objects.create(name='VAT 19%', region=region, rate_percent=Decimal('19'))

    def test_the_order_keeps_each_rate(self):
        address = {'country': 'DE'}
        order = OrderService.create_from_cart(self.cart, 'buyer@example.com', address, address)
        lines = [(line['label'], line['amount']) for line in order.tax_lines]
        self.assertEqual(lines, [('VAT 19%', Money(Decimal('3.80'), 'EUR'))])
        self.assertEqual(order.tax_total, Money(Decimal('3.80'), 'EUR'))

    def test_an_untaxed_order_keeps_no_lines(self):
        address = {'country': 'FR'}
        order = OrderService.create_from_cart(self.cart, 'buyer@example.com', address, address)
        self.assertEqual(order.tax_lines, [])
        self.assertNotIn('tax_lines', order.metadata)


class TaxLinesMustAddUpTests(TestCase):
    def _order(self, tax_lines, tax_total='3.80'):
        return Order(
            email='buyer@example.com',
            subtotal=Money(Decimal('20.00'), 'EUR'),
            tax_total=Money(Decimal(tax_total), 'EUR'),
            total=Money(Decimal('23.80'), 'EUR'),
            metadata={'tax_lines': tax_lines},
        )

    def test_lines_that_add_up_are_shown(self):
        order = self._order([{'label': 'VAT 19%', 'amount': '3.80'}])
        self.assertEqual([line['label'] for line in order.tax_lines], ['VAT 19%'])

    def test_lines_that_do_not_add_up_are_not(self):
        # Something after checkout changed the tax; the lines no longer prove it.
        self.assertEqual(self._order([{'label': 'VAT 19%', 'amount': '3.80'}], '0').tax_lines, [])

    def test_a_malformed_line_drops_them_all(self):
        order = self._order([{'label': 'VAT 19%', 'amount': '3.80'}, {'label': 'Broken'}])
        self.assertEqual(order.tax_lines, [])

"""Tax must apply to a real checkout address.

Every checkout path builds the address with the subdivision under ``state``;
the tax handler read only ``region``, so a state or province rate never
matched a real order and only a country-wide rate could apply. This runs a
real cart through the whole ``CART_CALCULATE_BREAKDOWN`` chain rather than
calling the tax service with ``region=`` directly, which is how the gap hid.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Cart, CartItem
from plugins.installed.orders.services import OrderService
from plugins.installed.tax.models import TaxRate, TaxRegion


class StateAddressTaxTests(TestCase):
    def setUp(self):
        product = Product.objects.create(
            name='Taxed Book',
            slug='taxed-book',
            sku='TAX-1',
            price=Money(Decimal('10.00'), 'USD'),
            status='active',
        )
        self.cart = Cart.objects.create(session_key='tax-state')
        CartItem.objects.create(
            cart=self.cart, product=product, quantity=1, unit_price=Money(Decimal('10.00'), 'USD')
        )
        region = TaxRegion.objects.create(name='New York', country='US', region='NY')
        TaxRate.objects.create(name='NY sales tax', region=region, rate_percent=Decimal('10'))

    def _tax(self, address):
        breakdown = OrderService.calculate_cart_breakdown(cart=self.cart, address=address)
        return breakdown['tax'].amount, breakdown['total'].amount

    def test_a_state_rate_applies_to_the_checkout_address(self):
        tax, total = self._tax({'country': 'US', 'state': 'NY'})
        self.assertEqual(tax, Decimal('1.00'))
        self.assertEqual(total, Decimal('11.00'))

    def test_the_state_code_matches_in_any_case(self):
        tax, _ = self._tax({'country': 'us', 'state': 'ny'})
        self.assertEqual(tax, Decimal('1.00'))

    def test_another_state_is_not_taxed_by_it(self):
        tax, total = self._tax({'country': 'US', 'state': 'CA'})
        self.assertEqual(tax, Decimal('0.00'))
        self.assertEqual(total, Decimal('10.00'))

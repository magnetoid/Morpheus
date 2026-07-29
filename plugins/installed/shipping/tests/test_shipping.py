"""Shipping plugin tests."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from morpheus.core import agent_registry
from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Cart, CartItem
from plugins.installed.shipping.models import ShippingRate, ShippingZone
from plugins.installed.shipping.services import list_available_rates

User = get_user_model()


def _setup_cart_with_one_item(amount='25'):
    user = User.objects.create_user(username='shop', email='shop@example.com', password='x')
    cart = Cart.objects.create(customer=user)
    p = Product.objects.create(
        name='Book',
        slug='book',
        sku='B',
        price=Money(Decimal(amount), 'USD'),
        status='active',
    )
    CartItem.objects.create(cart=cart, product=p, quantity=2, unit_price=p.price)
    return cart


class ShippingZoneMatchingTests(TestCase):
    def test_country_only_zone_matches(self):
        z = ShippingZone.objects.create(name='US', countries=['US'], regions=[])
        self.assertTrue(z.matches('US'))
        self.assertFalse(z.matches('CA'))

    def test_catchall_zone_matches_anything(self):
        z = ShippingZone.objects.create(name='Worldwide', countries=['*'], regions=[])
        self.assertTrue(z.matches('US'))
        self.assertTrue(z.matches('JP'))


class ShippingRateQuoteTests(TestCase):
    def test_flat_rate_quote(self):
        cart = _setup_cart_with_one_item('25')
        z = ShippingZone.objects.create(name='US', countries=['US'])
        ShippingRate.objects.create(
            zone=z,
            name='Standard',
            computation='flat',
            flat_amount=Money(Decimal('5.99'), 'USD'),
        )
        rates = list_available_rates(cart=cart, country='US')
        self.assertEqual(len(rates), 1)
        self.assertEqual(rates[0]['amount'].amount, Decimal('5.99'))

    def test_free_over_threshold(self):
        cart = _setup_cart_with_one_item('40')  # 2 × 40 = 80 subtotal
        z = ShippingZone.objects.create(name='US', countries=['US'])
        ShippingRate.objects.create(
            zone=z,
            name='Free over $50',
            computation='free_over',
            free_threshold=Money(Decimal('50'), 'USD'),
            flat_amount=Money(Decimal('7'), 'USD'),
        )
        rates = list_available_rates(cart=cart, country='US')
        self.assertEqual(len(rates), 1)
        self.assertEqual(rates[0]['amount'].amount, Decimal('0'))

    def test_order_total_tier(self):
        cart = _setup_cart_with_one_item('30')  # 60 subtotal
        z = ShippingZone.objects.create(name='US', countries=['US'])
        ShippingRate.objects.create(
            zone=z,
            name='Tiered',
            computation='order_total_tier',
            tiers=[
                {'threshold': '0', 'amount': '10'},
                {'threshold': '50', 'amount': '5'},
                {'threshold': '100', 'amount': '0'},
            ],
        )
        rates = list_available_rates(cart=cart, country='US')
        self.assertEqual(rates[0]['amount'].amount, Decimal('5'))


class ShippingAgentToolsTests(TestCase):
    def test_tools_registered(self):
        names = {t.name for t in agent_registry.platform_tools()}
        self.assertIn('shipping.list_zones', names)
        self.assertIn('shipping.add_flat_rate', names)

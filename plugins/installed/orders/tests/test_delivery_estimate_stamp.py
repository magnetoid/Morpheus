"""The order keeps the delivery estimate the shopper chose (F5).

Shipping puts `meta['delivery_estimate']` on the cart breakdown; the order copies
it into its metadata when it is placed, so the order page and the email show
what was promised, whatever the rate says later.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Order
from plugins.installed.orders.services import CartService, OrderService, _order_metadata


def _with(meta) -> dict:
    return _order_metadata('', {'meta': meta})


class StampTests(TestCase):
    def test_valid_meta_is_stamped(self):
        out = _with({'delivery_estimate': {'min': 3, 'max': 6}})
        self.assertEqual(out['delivery_estimate'], {'min': 3, 'max': 6})

    def test_invalid_meta_is_dropped(self):
        for bad in ({'min': 'x', 'max': 2}, {'min': 4, 'max': 2}, {'min': -1, 'max': 2}, '3-6'):
            self.assertNotIn('delivery_estimate', _with({'delivery_estimate': bad}), bad)

    def test_no_meta_no_key(self):
        self.assertNotIn('delivery_estimate', _with({}))

    def test_property_reads_the_stamp_even_with_the_setting_off(self):
        order = Order(metadata={'delivery_estimate': {'min': 3, 'max': 6}})
        self.assertEqual(order.delivery_estimate, {'min': 3, 'max': 6})
        self.assertIsNone(
            Order(metadata={'delivery_estimate': {'min': 9, 'max': 1}}).delivery_estimate
        )
        self.assertIsNone(Order(metadata={}).delivery_estimate)


class EndToEndTests(TestCase):
    def test_end_to_end_from_cart(self):
        from plugins.installed.shipping.models import ShippingRate, ShippingZone
        from plugins.models import PluginConfig

        PluginConfig.objects.update_or_create(
            plugin_name='shipping', defaults={'config': {'show_delivery_estimate': True}}
        )
        product = Product.objects.create(
            name='Parcel Book',
            slug='parcel-book',
            sku='PB-1',
            price=Money(Decimal('10'), 'USD'),
            status='active',
            requires_shipping=True,
        )
        zone = ShippingZone.objects.create(name='US', countries=['US'])
        rate = ShippingRate.objects.create(
            zone=zone,
            name='Courier',
            computation='flat',
            flat_amount=Money(5, 'USD'),
            estimated_days_min=2,
            estimated_days_max=5,
        )
        cart = CartService.get_or_create_cart(session_key='est1')
        CartService.add_item(cart, str(product.id), quantity=1)
        cart.metadata = {**(cart.metadata or {}), 'shipping_rate_id': str(rate.id)}
        cart.save()
        addr = {'first_name': 'S', 'last_name': 'T', 'line1': '1 Main', 'country': 'US'}
        order = OrderService.create_from_cart(cart, 'a@x.test', addr, addr)
        self.assertEqual(order.metadata['delivery_estimate'], {'min': 2, 'max': 5})
        self.assertEqual(Order.objects.get(pk=order.pk).delivery_estimate, {'min': 2, 'max': 5})

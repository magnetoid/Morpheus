"""Pre-launch products: shown, not sold.

While a store is being set up, a product marked "hide from search engines"
(``Product.noindex``) can be a preview: its page is visible, it cannot be
bought. The Irving theme hid its add-to-cart form for such products (02f239f),
but the cart still took them from every other path — a crafted POST, GraphQL,
an agent's checkout. With the orders setting ``prelaunch_noindex_not_for_sale``
on, the cart refuses them, and an order cannot be placed with one already in a
cart. Off (the default), noindex is only an SEO choice and the product sells.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Order
from plugins.installed.orders.services import CartService, OrderService

_KEY = 'prelaunch_noindex_not_for_sale'
_ADDR = {
    'first_name': 'A',
    'last_name': 'B',
    'address_line_1': '1 St',
    'city': 'Town',
    'postal_code': '11000',
    'country': 'US',
}


class PrelaunchProductTests(TestCase):
    def setUp(self):
        from plugins.registry import app_registry

        self.preview = Product.objects.create(
            name='Preview kit',
            slug='preview-kit',
            sku='PRE-1',
            status='active',
            price=Money(Decimal('25.00'), 'USD'),
            noindex=True,
        )
        self.ready = Product.objects.create(
            name='Ready kit',
            slug='ready-kit',
            sku='RDY-1',
            status='active',
            price=Money(Decimal('10.00'), 'USD'),
        )
        self.orders = app_registry.get('orders')
        # The config cache is per process: drop whatever this test leaves in it,
        # so the next test reads the rolled-back row rather than our switch.
        self.addCleanup(self.orders.invalidate_config_cache)

    def _switch_on(self):
        self.orders.set_config(_KEY, True)

    def test_off_a_noindex_product_still_sells(self):
        cart = CartService.get_or_create_cart(session_key='pre-off')
        CartService.add_item(cart, str(self.preview.id))
        self.assertEqual(cart.items.count(), 1)

    def test_on_the_cart_refuses_a_preview_and_takes_the_rest(self):
        self._switch_on()
        cart = CartService.get_or_create_cart(session_key='pre-on')
        with self.assertRaisesMessage(ValueError, 'not available to buy yet'):
            CartService.add_item(cart, str(self.preview.id))
        self.assertEqual(cart.items.count(), 0)

        CartService.add_item(cart, str(self.ready.id))
        self.assertEqual(cart.items.count(), 1)

    def test_on_no_order_with_a_preview_already_in_the_cart(self):
        cart = CartService.get_or_create_cart(session_key='pre-cart')
        CartService.add_item(cart, str(self.preview.id))  # carted while the switch was off
        self._switch_on()
        with self.assertRaisesMessage(ValueError, 'Preview kit'):
            OrderService.create_from_cart(cart, 'buyer@example.com', _ADDR, _ADDR)
        self.assertFalse(Order.objects.exists())

    def test_a_switch_flipped_by_another_process_is_seen(self):
        from plugins.models import PluginConfig

        self.orders.get_config()  # this process has cached the switch as off
        # Another gunicorn worker saves the setting: the row changes, this
        # process's cache does not.
        row, _ = PluginConfig.objects.get_or_create(plugin_name='orders')
        row.config = {**(row.config or {}), _KEY: True}
        row.save()

        cart = CartService.get_or_create_cart(session_key='pre-fresh')
        with self.assertRaises(ValueError):
            CartService.add_item(cart, str(self.preview.id))

    def test_the_storefront_add_to_cart_refuses_a_preview(self):
        self._switch_on()
        resp = self.client.post(
            f'/cart/add/{self.preview.id}/', {'quantity': 1}, HTTP_X_REQUESTED_WITH='fetch'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('not available to buy yet', resp.json()['error'])

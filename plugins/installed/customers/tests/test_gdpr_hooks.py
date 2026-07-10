"""GDPR export/erasure assemble via hooks; login cart-merge is orders-owned.

CUSTOMER_DATA_EXPORT / CUSTOMER_ANONYMISE let every plugin contribute its
own slice, so customers/services.py imports no sibling plugin and a
disabled plugin's data drops out of the export automatically. The guest
cart hand-off on login moved to orders (CUSTOMER_LOGIN subscriber) —
customers no longer imports orders (the old requires-cycle in reverse).
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from djmoney.money import Money

from core.hooks import MorpheusEvents, hook_registry
from plugins.installed.customers.services import anonymise_customer, gather_customer_data
from plugins.registry import plugin_registry


def _customer(email='c@example.com'):
    return get_user_model().objects.create_user(username=email, email=email, password='x')


class ExportHookTests(TestCase):
    def test_export_contains_plugin_slices(self):
        c = _customer()
        out = gather_customer_data(c)
        self.assertIn('account.json', out)
        self.assertIn('addresses.json', out)
        for contributed in (
            'orders.json',
            'reviews.json',
            'consent.json',
            'wishlist.json',
            'loyalty.json',
            'affiliate.json',
        ):
            self.assertIn(contributed, out)

    def test_disabled_plugin_slice_drops_out(self):
        c = _customer()
        self.addCleanup(plugin_registry.activate, 'wishlist')
        plugin_registry.deactivate('wishlist')
        out = gather_customer_data(c)
        self.assertNotIn('wishlist.json', out)
        self.assertIn('orders.json', out)  # other owners unaffected


class AnonymiseHookTests(TestCase):
    def test_plugin_rows_scrubbed_and_customer_anonymised(self):
        from plugins.installed.orders.models import Order
        from plugins.installed.wishlist.models import Wishlist

        c = _customer('erase-me@example.com')
        order = Order.objects.create(
            customer=c,
            email=c.email,
            customer_notes='call me on 555-1234',
            subtotal=Money(Decimal('10'), 'USD'),
            total=Money(Decimal('10'), 'USD'),
        )
        Wishlist.objects.create(customer=c, name='Default')

        anonymise_customer(c)

        # (re-fetch — django-fsm forbids refresh_from_db on `status`)
        order = Order.objects.get(pk=order.pk)
        self.assertNotIn('erase-me', order.email)
        self.assertEqual(order.customer_notes, '[redacted]')
        self.assertFalse(Wishlist.objects.filter(customer=c).exists())
        c.refresh_from_db()
        self.assertFalse(c.is_active)
        self.assertEqual(c.first_name, 'Deleted')
        self.assertNotIn('erase-me', c.email)


class LoginCartMergeTests(TestCase):
    def test_session_cart_adopted_on_login_event(self):
        from plugins.installed.orders.models import Cart

        c = _customer('login@example.com')
        request = RequestFactory().get('/')

        class _Session:
            session_key = 'sess-abc'

        request.session = _Session()
        cart = Cart.objects.create(session_key='sess-abc')

        hook_registry.fire(MorpheusEvents.CUSTOMER_LOGIN, customer=c, request=request)

        cart.refresh_from_db()
        self.assertEqual(cart.customer_id, c.pk)
        self.assertEqual(cart.session_key, '')

    def test_merge_skipped_when_orders_disabled(self):
        from plugins.installed.orders.models import Cart

        c = _customer('login2@example.com')
        request = RequestFactory().get('/')

        class _Session:
            session_key = 'sess-def'

        request.session = _Session()
        cart = Cart.objects.create(session_key='sess-def')

        self.addCleanup(plugin_registry.activate, 'orders')
        plugin_registry.deactivate('orders')
        hook_registry.fire(MorpheusEvents.CUSTOMER_LOGIN, customer=c, request=request)

        cart.refresh_from_db()
        self.assertIsNone(cart.customer_id)

"""What orders asks for at checkout, and who may check out (orders/checkout_fields.py).

The note, the gift message and the terms tick each appear only while their setting is
on; ``completeOrder`` keeps the answers on the order and refuses an order without a
required one, or from a guest while the store takes no guest orders.
"""

from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase
from djmoney.money import Money

from core import checkout_fields
from plugins.installed.catalog.models import Product
from plugins.installed.customers.models import Customer
from plugins.installed.orders.graphql.inputs import AddressInput
from plugins.installed.orders.graphql.mutations import (
    CompleteOrderInput,
    OrdersMutationExtension,
)
from plugins.installed.orders.models import Cart, CartItem, Order
from plugins.testing import set_app_settings

ROUTER = 'plugins.installed.payments.services.routing.create_payment_intent_for'


class FieldsTests(TestCase):
    def keys(self):
        return [f['key'] for f in checkout_fields.fields()]

    def test_a_new_store_asks_for_nothing_more(self):
        self.assertEqual(self.keys(), [])

    def test_each_setting_adds_its_field(self):
        set_app_settings(self, 'orders', checkout_order_notes=True)
        self.assertEqual(self.keys(), ['order_notes'])
        set_app_settings(self, 'orders', checkout_gift_message=True)
        self.assertEqual(self.keys(), ['order_notes', 'gift_message'])

    def test_terms_are_a_required_tick_with_their_link(self):
        set_app_settings(self, 'orders', checkout_terms_url='/pages/terms/')
        (terms,) = checkout_fields.fields()
        self.assertEqual(terms['key'], 'terms_accepted')
        self.assertTrue(terms['required'])
        self.assertEqual(terms['link_url'], '/pages/terms/')


class CompleteOrderTests(TestCase):
    def setUp(self):
        self.session = SessionStore()
        self.session.create()
        product = Product.objects.create(
            name='Field Book', slug='field-book', sku='FIELD-1',
            price=Money(Decimal('20.00'), 'USD'), status='active',
        )  # fmt: skip
        self.cart = Cart.objects.create(session_key=self.session.session_key)
        CartItem.objects.create(
            cart=self.cart, product=product, quantity=1, unit_price=Money(Decimal('20.00'), 'USD')
        )

    def place(self, answers=None, user=None):
        request = RequestFactory().post('/graphql/')
        request.session = self.session
        request.user = user or AnonymousUser()
        info = mock.Mock()
        info.context = {'request': request}
        inp = CompleteOrderInput(
            cart_id=str(self.cart.pk),
            email='buyer@example.com',
            shipping_address=AddressInput(first_name='Ana', line1='1 Main St', country='US'),
            checkout_fields=answers,
        )
        with mock.patch(ROUTER, return_value={'success': True, 'client_secret': 'cs_x'}):
            return OrdersMutationExtension().complete_order(info, inp)

    def test_the_answers_are_kept_on_the_order(self):
        set_app_settings(
            self, 'orders',
            checkout_order_notes=True, checkout_gift_message=True,
            checkout_terms_url='/pages/terms/',
        )  # fmt: skip
        result = self.place(
            {
                'order_notes': 'Leave it at the door',
                'gift_message': 'Happy birthday, Ana',
                'terms_accepted': True,
                'is_staff': True,
            }
        )
        self.assertFalse(result.errors, msg=str(result.errors))
        order = Order.objects.get(order_number=result.order_number)
        self.assertEqual(order.customer_notes, 'Leave it at the door')
        self.assertEqual(order.gift_message, 'Happy birthday, Ana')
        self.assertEqual(
            order.metadata['checkout_fields'],
            {
                'order_notes': 'Leave it at the door',
                'gift_message': 'Happy birthday, Ana',
                'terms_accepted': True,
            },
        )
        self.assertEqual(order.metadata['terms_accepted']['url'], '/pages/terms/')
        self.assertIn('at', order.metadata['terms_accepted'])

    def test_without_the_terms_tick_no_order_is_placed(self):
        set_app_settings(self, 'orders', checkout_terms_url='/pages/terms/')
        result = self.place({})
        self.assertEqual([e.code for e in result.errors], ['CHECKOUT_FIELDS'])
        self.assertIn('terms', result.errors[0].message)
        self.assertFalse(Order.objects.exists())

    def test_a_field_switched_off_stores_nothing(self):
        result = self.place({'order_notes': 'Typed by a script'})
        order = Order.objects.get(order_number=result.order_number)
        self.assertEqual(order.customer_notes, '')
        self.assertNotIn('checkout_fields', order.metadata)

    def test_a_guest_is_refused_while_the_store_takes_no_guest_orders(self):
        set_app_settings(self, 'orders', allow_guest_checkout=False)
        result = self.place()
        self.assertEqual([e.code for e in result.errors], ['SIGN_IN_REQUIRED'])
        self.assertFalse(Order.objects.exists())

    def test_a_signed_in_shopper_still_checks_out(self):
        set_app_settings(self, 'orders', allow_guest_checkout=False)
        shopper = Customer.objects.create_user(
            email='ana@example.com', username='ana', password='x'
        )
        self.cart.customer = shopper
        self.cart.save(update_fields=['customer'])
        result = self.place(user=shopper)
        self.assertFalse(result.errors, msg=str(result.errors))


class PackingSlipTests(TestCase):
    def test_the_slip_and_the_order_page_show_the_gift_message(self):
        staff = Customer.objects.create_user(
            username='ops', email='ops@example.com', password='x', is_staff=True
        )
        self.client.force_login(staff)
        order = Order.objects.create(
            email='buyer@example.com',
            subtotal=Money(Decimal('8.00'), 'USD'),
            total=Money(Decimal('8.00'), 'USD'),
            metadata={
                'checkout_fields': {'gift_message': 'Happy birthday, Ana', 'terms_accepted': True},
                'terms_accepted': {'url': '/pages/terms/', 'at': '2026-11-14T10:00:00+00:00'},
            },
        )
        url = f'/dashboard/orders/{order.order_number}/'
        slip = self.client.get(f'{url}packing-slip/').content.decode()
        self.assertIn('data-gift-message', slip)
        self.assertIn('Happy birthday, Ana', slip)
        page = self.client.get(url).content.decode()
        self.assertIn('Happy birthday, Ana', page)
        self.assertIn('Accepted the terms (/pages/terms/)', page)

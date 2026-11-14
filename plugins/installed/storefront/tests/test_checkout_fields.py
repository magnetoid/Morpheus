"""The checkout forms ask the apps' extra fields and send the answers on.

`{% checkout_fields %}` sits inside the review form and the one-page form of every theme;
the views pass the ``cf_<key>`` inputs to ``completeOrder``. While the store takes no
guest orders, every checkout step sends a shopper who is not signed in to sign-in first.
"""

from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.apps import apps
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.customers.models import Customer
from plugins.installed.orders.models import Order
from plugins.testing import set_app_settings
from themes.registry import theme_registry

ROUTER = 'plugins.installed.payments.services.routing.create_payment_intent_for'
THEMES = ['dot_books', 'supernatural_shop']
if apps.is_installed('plugins.installed.booking_marketplace'):
    THEMES += ['montenegro', 'croatia']

ADDRESS = {
    'email': 'buyer@example.com',
    'first_name': 'Ana',
    'last_name': 'Kovač',
    'address_line1': '1 Main Street',
    'city': 'Belgrade',
    'postal_code': '11000',
    'country': 'RS',
}


class _Cart(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Field Book', slug='field-book', sku='FIELD-1',
            price=Money(Decimal('12.00'), 'USD'), status='active',
        )  # fmt: skip
        self.client.post(f'/cart/add/{self.product.id}/', {'quantity': 1})
        set_app_settings(
            self, 'orders', checkout_order_notes=True, checkout_terms_url='/pages/terms/'
        )


class OnePageTests(_Cart):
    def test_the_form_asks_for_the_fields(self):
        body = self.client.get('/checkout/quick/').content.decode()
        self.assertIn('name="cf_order_notes"', body)
        self.assertIn('name="cf_terms_accepted"', body)
        self.assertIn('href="/pages/terms/"', body)

    def test_the_answers_reach_the_order(self):
        with mock.patch(ROUTER, return_value={'success': True, 'client_secret': 'cs_x'}):
            response = self.client.post(
                '/checkout/quick/',
                {**ADDRESS, 'cf_order_notes': 'Ring twice', 'cf_terms_accepted': '1'},
            )
        self.assertEqual(response.status_code, 302, response.content[:500])
        order = Order.objects.get()
        self.assertEqual(order.customer_notes, 'Ring twice')
        self.assertTrue(order.metadata['checkout_fields']['terms_accepted'])

    def test_without_the_tick_the_form_comes_back_with_what_was_typed(self):
        with mock.patch(ROUTER, return_value={'success': True, 'client_secret': 'cs_x'}):
            response = self.client.post(
                '/checkout/quick/', {**ADDRESS, 'cf_order_notes': 'Ring twice'}
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please accept the terms and conditions')
        self.assertContains(response, 'Ring twice</textarea>')
        self.assertFalse(Order.objects.exists())


class ReviewStepTests(_Cart):
    def setUp(self):
        super().setUp()
        session = self.client.session
        session['checkout_address'] = ADDRESS
        session['checkout_shipping_rate_id'] = 'standard'
        session.save()

    def test_the_review_step_asks_and_sends_the_fields(self):
        self.assertContains(self.client.get('/checkout/review/'), 'name="cf_terms_accepted"')
        with mock.patch(ROUTER, return_value={'success': True, 'client_secret': 'cs_x'}):
            response = self.client.post(
                '/checkout/review/', {'cf_order_notes': 'Ring twice', 'cf_terms_accepted': '1'}
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.get().customer_notes, 'Ring twice')


class EveryThemeTests(_Cart):
    def test_every_theme_shows_the_fields_in_its_checkout_forms(self):
        session = self.client.session
        session['checkout_address'] = ADDRESS
        session.save()
        for name in THEMES:
            with self.subTest(theme=name):
                override = override_settings(MORPHEUS_ACTIVE_THEME=name)
                override.enable()
                previous = theme_registry._active_name
                theme_registry.set_active(name)
                try:
                    for url in ('/checkout/quick/', '/checkout/review/'):
                        response = self.client.get(url, follow=True)
                        self.assertContains(response, 'name="cf_terms_accepted"')
                finally:
                    theme_registry._active_name = previous
                    override.disable()


class GuestCheckoutTests(_Cart):
    def test_a_guest_signs_in_first_while_the_store_takes_no_guest_orders(self):
        set_app_settings(self, 'orders', allow_guest_checkout=False)
        for url in ('/checkout/', '/checkout/shipping/', '/checkout/review/', '/checkout/quick/'):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response['Location'].startswith('/auth/login/?next='))

    def test_a_signed_in_shopper_goes_straight_to_checkout(self):
        set_app_settings(self, 'orders', allow_guest_checkout=False)
        self.client.force_login(
            Customer.objects.create_user(email='ana@example.com', username='ana', password='x')
        )
        self.assertEqual(self.client.get('/checkout/quick/').status_code, 200)

    def test_guests_are_welcome_by_default(self):
        self.assertEqual(self.client.get('/checkout/quick/').status_code, 200)

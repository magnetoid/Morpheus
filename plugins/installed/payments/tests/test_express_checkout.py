"""Express checkout on the cart page: the wallet charges what its sheet showed.

The cart offers Apple Pay / Google Pay / Link (Stripe's Express Checkout Element)
only while Stripe can take the payment. Every amount the sheet shows comes from the
server for the wallet's address, and the order is placed only while that amount
still holds; the order's total is what the PaymentIntent charges.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from unittest import mock

from django.test import Client, TestCase, override_settings
from djmoney.money import Money

from core.models import StoreSettings
from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Cart, Order
from plugins.installed.shipping.models import ShippingRate, ShippingZone
from plugins.registry import app_registry

FAKE_SECRET, FAKE_PUBLIC = 'sk_test_x', 'pk_test_x'
STRIPE_READY = override_settings(STRIPE_SECRET_KEY=FAKE_SECRET, STRIPE_PUBLIC_KEY=FAKE_PUBLIC)
NO_STRIPE = override_settings(STRIPE_SECRET_KEY='', STRIPE_PUBLIC_KEY='')
ADDRESS = {'city': 'New York', 'state': 'NY', 'postal_code': '10001', 'country': 'US'}


class _FakeIntent:
    id = 'pi_test_express'
    client_secret = 'pi_test_express_secret'


def _stripe_intent():
    return mock.patch(
        'plugins.installed.payments.services.stripe.stripe.PaymentIntent.create',
        return_value=_FakeIntent(),
    )


def _config(response) -> dict:
    match = re.search(
        r'<script id="express-checkout-config" type="application/json">(.*?)</script>',
        response.content.decode(),
        re.S,
    )
    return json.loads(match.group(1)) if match else {}


class _Cart(TestCase):
    """A $12 book in the cart, delivered in the US for $5 (standard) or $15 (express)."""

    digital = False

    def setUp(self):
        StoreSettings.objects.create(country='US')
        zone = ShippingZone.objects.create(name='US', countries=['US'])
        self.standard = ShippingRate.objects.create(
            zone=zone,
            name='Standard',
            computation='flat',
            flat_amount=Money(Decimal('5.00'), 'USD'),
            priority=10,
        )
        self.express = ShippingRate.objects.create(
            zone=zone,
            name='Express',
            computation='flat',
            flat_amount=Money(Decimal('15.00'), 'USD'),
            priority=20,
        )
        self.product = Product.objects.create(
            name='Express Book',
            slug='express-book',
            sku='EX-1',
            price=Money(Decimal('12.00'), 'USD'),
            status='active',
            requires_shipping=not self.digital,
        )
        self.client.post(f'/cart/add/{self.product.id}/', {'quantity': 1})

    def quote(self, address=None, rate_id=''):
        return self.client.post(
            '/payments/express/quote/',
            json.dumps({'address': address or ADDRESS, 'rateId': rate_id}),
            content_type='application/json',
        )

    def place(self, amount, rate_id, **overrides):
        body = {
            'billingDetails': {
                'name': 'Ada Lovelace',
                'email': 'ada@example.com',
                'phone': '+1 555 0100',
                'address': {**ADDRESS, 'line1': '1 Main St'},
            },
            'shippingAddress': {
                'name': 'Ada Lovelace',
                'address': {**ADDRESS, 'line1': '1 Main St', 'line2': 'Apt 4'},
            },
            'rateId': rate_id,
            'amount': amount,
            **overrides,
        }
        with _stripe_intent():
            return self.client.post(
                '/payments/express/order/', json.dumps(body), content_type='application/json'
            )


@STRIPE_READY
class CartPageTests(_Cart):
    def test_the_cart_offers_the_wallets_with_the_total_for_the_store_country(self):
        response = self.client.get('/cart/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-express-checkout')
        self.assertContains(response, 'payments/express-cart.js')
        config = _config(response)
        self.assertEqual(config['key'], FAKE_PUBLIC)
        self.assertEqual(config['currency'], 'usd')
        self.assertTrue(config['ships'])
        # $12 + $5 standard delivery, in cents; the first choice is what it is for.
        self.assertEqual(config['amount'], 1700)
        self.assertEqual(config['rateId'], str(self.standard.id))
        self.assertEqual(
            [(r['displayName'], r['amount']) for r in config['shippingRates']],
            [('Standard', 500), ('Express', 1500)],
        )
        self.assertEqual(config['quoteUrl'], '/payments/express/quote/')
        self.assertEqual(config['orderUrl'], '/payments/express/order/')

    def test_the_merchant_can_switch_them_off(self):
        plugin = app_registry.get('payments')
        plugin.set_config('express_on_cart', False)
        self.addCleanup(plugin.invalidate_config_cache)
        self.assertNotContains(self.client.get('/cart/'), 'data-express-checkout')

    def test_a_cart_that_needs_the_withdrawal_tick_goes_through_the_form(self):
        orders = app_registry.get('orders')
        orders.set_config('digital_withdrawal_waiver_enabled', True)
        self.addCleanup(orders.invalidate_config_cache)
        ebook = Product.objects.create(
            name='Express Ebook',
            slug='express-ebook',
            sku='EX-2',
            price=Money(Decimal('4.00'), 'USD'),
            status='active',
            requires_shipping=False,
        )
        self.client.post(f'/cart/add/{ebook.id}/', {'quantity': 1})
        self.assertNotContains(self.client.get('/cart/'), 'data-express-checkout')

    def test_nothing_is_offered_while_the_app_is_off(self):
        app_registry.deactivate('payments')
        self.addCleanup(app_registry.activate, 'payments')
        self.assertNotContains(self.client.get('/cart/'), 'data-express-checkout')


@NO_STRIPE
class WithoutStripeTests(_Cart):
    def test_no_wallets_without_stripe(self):
        response = self.client.get('/cart/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-express-checkout')

    def test_no_order_without_stripe(self):
        response = self.place(1700, str(self.standard.id))
        self.assertEqual(response.status_code, 409)
        self.assertFalse(Order.objects.exists())


@STRIPE_READY
class QuoteTests(_Cart):
    def test_an_address_gets_its_delivery_choices_and_the_total(self):
        response = self.quote()
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['amount'], 1700)
        self.assertEqual(data['rateId'], str(self.standard.id))
        self.assertEqual(len(data['shippingRates']), 2)

    def test_a_chosen_delivery_changes_the_total(self):
        data = self.quote(rate_id=str(self.express.id)).json()
        self.assertEqual(data['amount'], 2700)
        self.assertEqual(data['rateId'], str(self.express.id))

    def test_an_address_no_zone_covers_gets_the_checkouts_own_fallback(self):
        response = self.quote(address={'country': 'JP'})
        # No zone covers Japan: the checkout forms deliver free then, and so does this.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['amount'], 1200)

    def test_an_empty_cart_has_nothing_to_quote(self):
        Cart.objects.all().delete()
        self.assertEqual(self.quote().status_code, 404)

    def test_only_a_post(self):
        self.assertEqual(self.client.get('/payments/express/quote/').status_code, 405)

    def test_it_needs_the_csrf_token(self):
        browser = Client(enforce_csrf_checks=True)
        browser.cookies = self.client.cookies
        response = browser.post(
            '/payments/express/quote/',
            json.dumps({'address': ADDRESS}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)


@STRIPE_READY
class PlaceOrderTests(_Cart):
    def test_the_order_charges_exactly_what_the_sheet_showed(self):
        shown = self.quote(rate_id=str(self.express.id)).json()['amount']
        response = self.place(shown, str(self.express.id))
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data['clientSecret'], _FakeIntent.client_secret)
        order = Order.objects.get(order_number=data['orderNumber'])
        self.assertEqual(order.total, Money(Decimal('27.00'), 'USD'))
        self.assertEqual(order.shipping_total, Money(Decimal('15.00'), 'USD'))
        self.assertEqual(order.email, 'ada@example.com')
        self.assertEqual(order.shipping_address['line1'], '1 Main St')
        self.assertEqual(order.shipping_address['line2'], 'Apt 4')
        self.assertEqual(order.shipping_address['country'], 'US')
        self.assertEqual(order.shipping_address['first_name'], 'Ada')
        self.assertEqual(order.shipping_address['last_name'], 'Lovelace')
        self.assertEqual(
            Order.objects.values_list('payment_gateway', flat=True).get(pk=order.pk), 'stripe'
        )
        self.assertIn(f'/order/confirmation/{order.order_number}/?token=', data['returnUrl'])
        # A declined wallet carries on at the checkout's payment step.
        self.assertEqual(self.client.session['checkout_order_number'], order.order_number)
        self.assertEqual(self.client.session['checkout_client_secret'], _FakeIntent.client_secret)

    def test_a_total_that_changed_is_refused_with_the_new_one(self):
        response = self.place(1700, str(self.express.id))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['amount'], 2700)
        self.assertFalse(Order.objects.exists())
        self.assertTrue(Cart.objects.get().items.exists())

    def test_a_delivery_choice_no_longer_offered_is_refused(self):
        response = self.place(1700, 'gone')
        self.assertEqual(response.status_code, 409)
        self.assertFalse(Order.objects.exists())

    def test_a_wallet_without_an_email_is_refused(self):
        response = self.place(
            1700, str(self.standard.id), billingDetails={'name': 'Ada', 'address': ADDRESS}
        )
        self.assertEqual(response.status_code, 409)
        self.assertFalse(Order.objects.exists())

    def test_a_delivery_address_without_a_street_is_refused(self):
        response = self.place(
            1700, str(self.standard.id), shippingAddress={'name': 'Ada', 'address': ADDRESS}
        )
        self.assertEqual(response.status_code, 409)
        self.assertFalse(Order.objects.exists())

    def test_an_empty_cart_places_nothing(self):
        Cart.objects.all().delete()
        self.assertEqual(self.place(1700, str(self.standard.id)).status_code, 404)

    def test_a_quote_that_fails_is_refused_not_a_server_error(self):
        with mock.patch(
            'plugins.installed.payments.express.quote', side_effect=RuntimeError('boom')
        ):
            response = self.place(1700, str(self.standard.id))
        self.assertEqual(response.status_code, 409)
        self.assertFalse(Order.objects.exists())

    def test_nothing_to_charge_goes_through_the_form(self):
        free = {'amount': 0, 'currency': 'usd', 'shippingRates': [], 'rateId': ''}
        with mock.patch('plugins.installed.payments.express.quote', return_value=free):
            response = self.place(0, '')
        self.assertEqual(response.status_code, 409)
        self.assertFalse(Order.objects.exists())


@STRIPE_READY
class DigitalCartTests(_Cart):
    digital = True

    def test_a_download_needs_no_delivery_and_bills_the_wallet_address(self):
        config = _config(self.client.get('/cart/'))
        self.assertFalse(config['ships'])
        self.assertEqual(config['shippingRates'], [])
        self.assertEqual(config['amount'], 1200)
        response = self.place(1200, '', shippingAddress={})
        self.assertEqual(response.status_code, 200, response.content)
        order = Order.objects.get(order_number=response.json()['orderNumber'])
        self.assertEqual(order.total, Money(Decimal('12.00'), 'USD'))
        self.assertEqual(order.shipping_address['line1'], '1 Main St')

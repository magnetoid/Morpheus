"""Saved cards at checkout (payments' ``checkout_show_saved_cards`` and
``checkout_offer_save_card``, v0.155.0).

Until v0.155.0 the checkout's PaymentIntent named no Stripe customer, so a card
saved on the account page never showed at checkout and none could be saved there.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from plugins.registry import app_registry


def _intent():
    return SimpleNamespace(
        id='pi_saved', client_secret='pi_saved_secret', status='requires_payment_method'
    )


class SavedCardTests(TestCase):
    def setUp(self):
        self.payments = app_registry.get('payments')
        self.addCleanup(self.payments.invalidate_config_cache)
        self.payments.set_config('stripe_secret_key', 'sk_test_x')
        self.payments.set_config('stripe_public_key', 'pk_test_x')
        self.shopper = get_user_model().objects.create_user(
            username='saver', email='saver@example.com', password='x'
        )

    def _order(self, customer=None):
        from plugins.installed.orders.models import Order

        return Order.objects.create(
            email='saver@example.com',
            customer=customer,
            subtotal=Money(10, 'USD'),
            total=Money(10, 'USD'),
            payment_gateway='stripe',
        )

    def _start(self, order):
        from plugins.installed.payments.services.stripe import PaymentService

        with (
            mock.patch('stripe.PaymentIntent.create', return_value=_intent()) as create,
            mock.patch('stripe.Customer.create', return_value=SimpleNamespace(id='cus_1')),
        ):
            PaymentService.create_payment_intent(order)
        return create.call_args.kwargs

    def _session(self, order, user):
        from plugins.installed.payments.services.stripe import PaymentService

        order = type(order).objects.get(pk=order.pk)
        with mock.patch(
            'stripe.CustomerSession.create', return_value=SimpleNamespace(client_secret='cuss_1')
        ) as create:
            secret = PaymentService.checkout_customer_session(order, user)
        return secret, create

    def test_by_default_the_payment_names_no_customer(self):
        order = self._order(self.shopper)
        kwargs = self._start(order)
        self.assertNotIn('customer', kwargs)
        self.assertEqual(kwargs['idempotency_key'], f'pi-{order.id}-1000')
        self.assertEqual(self._session(order, self.shopper)[0], '')

    def test_saved_cards_show_for_the_signed_in_shopper(self):
        self.payments.set_config('checkout_show_saved_cards', True)
        order = self._order(self.shopper)
        kwargs = self._start(order)
        self.assertEqual(kwargs['customer'], 'cus_1')
        self.assertEqual(kwargs['idempotency_key'], f'pi-{order.id}-1000-cus_1')
        secret, create = self._session(order, self.shopper)
        self.assertEqual(secret, 'cuss_1')
        features = create.call_args.kwargs['components']['payment_element']['features']
        self.assertEqual(features['payment_method_redisplay'], 'enabled')
        self.assertEqual(features['payment_method_save'], 'disabled')
        self.assertEqual(features['payment_method_remove'], 'disabled')

    def test_offering_to_save_the_card(self):
        self.payments.set_config('checkout_offer_save_card', True)
        order = self._order(self.shopper)
        self._start(order)
        _, create = self._session(order, self.shopper)
        features = create.call_args.kwargs['components']['payment_element']['features']
        self.assertEqual(features['payment_method_save'], 'enabled')
        self.assertEqual(features['payment_method_save_usage'], 'off_session')
        self.assertEqual(features['payment_method_redisplay'], 'disabled')

    def test_a_guest_or_another_shopper_sees_no_saved_cards(self):
        self.payments.set_config('checkout_show_saved_cards', True)
        guest_order = self._order()
        self.assertNotIn('customer', self._start(guest_order))
        order = self._order(self.shopper)
        self._start(order)
        stranger = get_user_model().objects.create_user(
            username='stranger', email='s@example.com', password='x'
        )
        secret, create = self._session(order, stranger)
        self.assertEqual(secret, '')
        create.assert_not_called()

    def test_a_vault_failure_still_takes_the_payment(self):
        from plugins.installed.payments.services.stripe import PaymentService

        self.payments.set_config('checkout_show_saved_cards', True)
        order = self._order(self.shopper)
        with (
            mock.patch('stripe.PaymentIntent.create', return_value=_intent()) as create,
            mock.patch('stripe.Customer.create', side_effect=RuntimeError('down')),
        ):
            self.assertTrue(PaymentService.create_payment_intent(order)['success'])
        self.assertNotIn('customer', create.call_args.kwargs)

    def test_the_payment_page_hands_the_session_to_the_card_form(self):
        self.payments.set_config('checkout_show_saved_cards', True)
        order = self._order(self.shopper)
        self._start(order)
        self.client.force_login(self.shopper)
        session = self.client.session
        session['checkout_order_number'] = order.order_number
        session['checkout_client_secret'] = 'pi_saved_secret'
        session.save()
        with mock.patch(
            'stripe.CustomerSession.create', return_value=SimpleNamespace(client_secret='cuss_page')
        ):
            page = self.client.get('/checkout/payment/')
        self.assertContains(page, "customerSessionClientSecret: 'cuss_page'")

    def test_without_saved_cards_the_page_sends_no_session(self):
        order = self._order(self.shopper)
        self._start(order)
        self.client.force_login(self.shopper)
        session = self.client.session
        session['checkout_order_number'] = order.order_number
        session['checkout_client_secret'] = 'pi_saved_secret'
        session.save()
        page = self.client.get('/checkout/payment/')
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'customerSessionClientSecret')

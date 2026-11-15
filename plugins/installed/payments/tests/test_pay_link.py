"""The payment link's page, /pay/<token>/ (A8, v0.171.0).

A customer pays a placed order from it. A GET only shows (an email link scanner
opens every link); a POST starts the payment through the checkout's routing.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from django.apps import apps
from django.core import mail
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.orders.models import Order, OrderItem
from plugins.installed.orders.payment_deadline import KEY
from plugins.installed.payments import pay_link
from plugins.installed.payments.models import PaymentGatewayConfig, PaymentTransaction
from plugins.installed.payments.services.stripe import PaymentService
from themes.registry import theme_registry

THEMES = ['dot_books', 'supernatural_shop', 'irving_survival']
if apps.is_installed('plugins.installed.booking_marketplace'):
    THEMES += ['montenegro', 'croatia']

BANK_DETAILS = {'instructions': 'Pay to IBAN ME25 0000 1111 2222 3333 44'}
ROUTING = 'plugins.installed.payments.services.routing'


def _order(**kw):
    order = Order.objects.create(
        email='buyer@example.com',
        subtotal=Money(20, 'USD'),
        total=Money(20, 'USD'),
        **kw,
    )
    OrderItem.objects.create(
        order=order,
        product_name='Field Guide',
        sku='FG-1',
        unit_price=Money(10, 'USD'),
        quantity=2,
        total_price=Money(20, 'USD'),
    )
    return order


def _set(order, **fields):
    """Write fields without the protected FSM setter (Order.status)."""
    Order.objects.filter(pk=order.pk).update(**fields)
    return Order.objects.get(pk=order.pk)


def _bank_transfer_only():
    PaymentGatewayConfig.objects.update_or_create(
        slug='manual', defaults={'enabled': True, 'config': BANK_DETAILS}
    )
    PaymentGatewayConfig.objects.update_or_create(slug='stripe', defaults={'enabled': False})


class PayPageTests(TestCase):
    def setUp(self):
        self.order = _order()
        self.url = f'/pay/{self.order.public_token}/'

    def test_an_unknown_token_is_not_found(self):
        self.assertEqual(self.client.get(f'/pay/{"x" * 43}/').status_code, 404)
        self.assertEqual(self.client.get('/pay/short/').status_code, 404)

    def test_a_get_shows_the_order_and_starts_nothing(self):
        _bank_transfer_only()
        with mock.patch(f'{ROUTING}.create_payment_intent_for') as start:
            response = self.client.get(self.url)
        start.assert_not_called()
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn(f'Order #{self.order.order_number}', body)
        self.assertIn('Field Guide', body)
        self.assertIn('value="manual"', body)
        self.assertIn(BANK_DETAILS['instructions'], body)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('noindex', body)
        self.assertFalse(PaymentTransaction.objects.filter(order=self.order).exists())

    def test_bank_transfer_goes_to_the_confirmation(self):
        _bank_transfer_only()
        response = self.client.post(self.url, {'payment_method': 'manual'})
        self.assertRedirects(
            response,
            f'/order/confirmation/{self.order.order_number}/?token={self.order.public_token}',
            fetch_redirect_response=False,
        )
        gateway = Order.objects.values_list('payment_gateway', flat=True).get(pk=self.order.pk)
        self.assertEqual(gateway, 'manual')

    def test_a_card_goes_to_the_checkouts_payment_step(self):
        methods = [{'slug': 'stripe', 'label': 'Card', 'capability': '', 'instructions': ''}]
        with (
            mock.patch(
                f'{ROUTING}.picker_gateways', return_value=[{**methods[0], 'is_default': True}]
            ),
            mock.patch(
                f'{ROUTING}.create_payment_intent_for',
                return_value={'success': True, 'client_secret': 'pi_1_secret_2'},
            ) as start,
        ):
            response = self.client.post(self.url, {'payment_method': 'stripe'})
        self.assertRedirects(response, '/checkout/payment/', fetch_redirect_response=False)
        start.assert_called_once()
        self.assertEqual(start.call_args.args[1], 'stripe')
        session = self.client.session
        self.assertEqual(session['checkout_order_number'], self.order.order_number)
        self.assertEqual(session['checkout_client_secret'], 'pi_1_secret_2')

    def test_paypal_goes_to_its_approval_page(self):
        method = {'slug': 'paypal', 'label': 'PayPal', 'capability': '', 'instructions': ''}
        with (
            mock.patch(f'{ROUTING}.picker_gateways', return_value=[{**method, 'is_default': True}]),
            mock.patch(
                f'{ROUTING}.create_payment_intent_for',
                return_value={
                    'success': True,
                    'approval_url': 'https://www.paypal.com/approve?x=1',
                },
            ),
        ):
            response = self.client.post(self.url, {'payment_method': 'paypal'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'https://www.paypal.com/approve?x=1')

    def test_a_method_not_offered_is_refused(self):
        _bank_transfer_only()
        with mock.patch(f'{ROUTING}.create_payment_intent_for') as start:
            response = self.client.post(self.url, {'payment_method': 'test'})
        start.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertIn('Choose a way to pay.', response.content.decode())

    def test_a_failed_start_shows_the_reason_and_keeps_the_form(self):
        _bank_transfer_only()
        with mock.patch(
            f'{ROUTING}.create_payment_intent_for',
            return_value={'success': False, 'error': 'Card payment could not be started.'},
        ):
            response = self.client.post(self.url, {'payment_method': 'manual'})
        body = response.content.decode()
        self.assertIn('Card payment could not be started.', body)
        self.assertIn('value="manual"', body)

    def test_a_paid_order_offers_no_form_and_starts_nothing(self):
        _bank_transfer_only()
        _set(self.order, payment_status='paid')
        with mock.patch(f'{ROUTING}.create_payment_intent_for') as start:
            response = self.client.post(self.url, {'payment_method': 'manual'})
        start.assert_not_called()
        body = response.content.decode()
        self.assertIn('This order is paid', body)
        self.assertNotIn('value="manual"', body)

    def test_a_held_card_counts_as_paid(self):
        order = _set(self.order, payment_status='authorized')
        self.assertEqual(pay_link.state(order), 'paid')

    def test_a_cancelled_or_shipped_order_is_closed(self):
        _bank_transfer_only()
        for status in ('cancelled', 'shipped'):
            _set(self.order, status=status)
            body = self.client.get(self.url).content.decode()
            self.assertIn('This order is closed', body, status)
            self.assertNotIn('value="manual"', body)

    def test_a_released_hold_can_be_paid_again(self):
        order = _set(self.order, payment_status='released')
        self.assertEqual(pay_link.state(order), 'payable')

    def test_an_order_with_nothing_to_pay_offers_no_form(self):
        _bank_transfer_only()
        _set(self.order, total=Money(0, 'USD'))
        body = self.client.get(self.url).content.decode()
        self.assertIn('Nothing to pay', body)
        self.assertNotIn('value="manual"', body)


class PayPageEveryThemeTests(TestCase):
    """The page extends the active theme's base, so it must render under each."""

    def use_theme(self, name):
        override = override_settings(MORPHEUS_ACTIVE_THEME=name)
        override.enable()
        self.addCleanup(override.disable)
        previous = theme_registry._active_name
        self.addCleanup(setattr, theme_registry, '_active_name', previous)
        theme_registry.set_active(name)

    def test_the_page_renders_under_every_theme(self):
        _bank_transfer_only()
        order = _order()
        for theme in THEMES:
            with self.subTest(theme=theme):
                self.use_theme(theme)
                response = self.client.get(f'/pay/{order.public_token}/')
                self.assertEqual(response.status_code, 200)
                body = response.content.decode()
                self.assertIn(f'Order #{order.order_number}', body)
                self.assertIn('name="payment_method" value="manual"', body)


class StripeRowPerIntentTests(TestCase):
    """A second attempt at an order gets the same intent back from Stripe's
    idempotency key, and must not add a second pending row."""

    def test_one_row_per_intent(self):
        order = _order()
        intent = SimpleNamespace(id='pi_same', client_secret='pi_same_secret')
        with (
            mock.patch.object(PaymentService, 'get_stripe_api_key', return_value='sk_test_x'),
            mock.patch('stripe.PaymentIntent.create', return_value=intent),
        ):
            first = PaymentService.create_payment_intent(order)
            second = PaymentService.create_payment_intent(order)
        self.assertTrue(first['success'] and second['success'])
        self.assertEqual(first['transaction_id'], second['transaction_id'])
        self.assertEqual(PaymentTransaction.objects.filter(order=order).count(), 1)

    def test_a_released_hold_gets_a_fresh_intent(self):
        """Stripe cancels a released hold's intent; the same key would hand it back."""
        order = _order()
        intents = [
            SimpleNamespace(id='pi_first', client_secret='pi_first_secret'),
            SimpleNamespace(id='pi_fresh', client_secret='pi_fresh_secret'),
        ]
        with (
            mock.patch.object(PaymentService, 'get_stripe_api_key', return_value='sk_test_x'),
            mock.patch('stripe.PaymentIntent.create', side_effect=intents) as create,
        ):
            PaymentService.create_payment_intent(order)
            PaymentTransaction.objects.filter(provider_transaction_id='pi_first').update(
                status=PaymentTransaction.Status.RELEASED
            )
            retry = PaymentService.create_payment_intent(order)
        first_key = create.call_args_list[0].kwargs['idempotency_key']
        retry_key = create.call_args_list[1].kwargs['idempotency_key']
        self.assertNotEqual(first_key, retry_key)
        self.assertTrue(retry_key.endswith('-r1'), retry_key)
        self.assertEqual(retry['client_secret'], 'pi_fresh_secret')
        self.assertTrue(
            PaymentTransaction.objects.filter(
                provider_transaction_id='pi_fresh', status=PaymentTransaction.Status.PENDING
            ).exists()
        )


@override_settings(DEFAULT_FROM_EMAIL='shop@example.com')
class SendLinkTests(TestCase):
    def test_send_emails_the_link_holds_the_order_and_logs_it(self):
        order = _order()
        sent, reason = pay_link.send(order, kind='link')
        self.assertTrue(sent, reason)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['buyer@example.com'])
        self.assertIn(f'#{order.order_number}', message.subject)
        self.assertIn(f'/pay/{order.public_token}/', message.body)
        md = Order.objects.values_list('metadata', flat=True).get(pk=order.pk)
        self.assertIn(KEY, md)
        self.assertTrue(order.events.filter(event_type='PAYMENT_LINK_SENT').exists())

    def test_send_refuses_a_paid_order_and_one_without_email(self):
        paid = _set(_order(), payment_status='paid')
        self.assertEqual(pay_link.send(paid), (False, 'This order is already paid.'))
        no_email = _set(_order(), email='')
        sent, _ = pay_link.send(no_email)
        self.assertFalse(sent)
        self.assertEqual(mail.outbox, [])

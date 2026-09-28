"""ISO-4217 minor-unit conversion (zero-decimal double-charge fix).

``amount=1000`` means $10.00 in USD but ¥1000 in JPY — multiplying by 100
unconditionally overcharges zero-decimal currencies 100x and undercharges
three-decimal ones 10x. ``amount_to_minor`` is the single conversion point
for every amount the payments plugin sends to Stripe.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.orders.models import Order
from plugins.installed.payments.services.money import amount_to_minor
from plugins.installed.payments.services.stripe import PaymentService


class AmountToMinorTests(TestCase):
    def test_usd_two_decimal(self):
        m = Money('10.00', 'USD')
        self.assertEqual(amount_to_minor(m.amount, str(m.currency)), 1000)

    def test_jpy_zero_decimal(self):
        m = Money(1000, 'JPY')
        self.assertEqual(amount_to_minor(m.amount, str(m.currency)), 1000)

    def test_bhd_three_decimal(self):
        m = Money('1.234', 'BHD')
        self.assertEqual(amount_to_minor(m.amount, str(m.currency)), 1234)

    def test_rounds_half_up(self):
        self.assertEqual(amount_to_minor(Decimal('10.005'), 'USD'), 1001)
        self.assertEqual(amount_to_minor(Decimal('0.5'), 'JPY'), 1)


FAKE_SECRET = 'sk_test_x'  # not a real key


@override_settings(STRIPE_SECRET_KEY=FAKE_SECRET)
class CreatePaymentIntentMinorUnitsTests(TestCase):
    def test_jpy_intent_amount_is_not_multiplied_by_100(self):
        order = Order.objects.create(
            email='c@example.com',
            subtotal=Money(Decimal('1000'), 'JPY'),
            total=Money(Decimal('1000'), 'JPY'),
        )
        intent = SimpleNamespace(id='pi_jpy_ci', client_secret='cs_1')
        with mock.patch('stripe.PaymentIntent.create', return_value=intent) as create:
            result = PaymentService.create_payment_intent(order)
        self.assertTrue(result['success'])
        self.assertEqual(create.call_args.kwargs['amount'], 1000)
        self.assertEqual(create.call_args.kwargs['currency'], 'jpy')
        self.assertEqual(create.call_args.kwargs['idempotency_key'], f'pi-{order.id}-1000')

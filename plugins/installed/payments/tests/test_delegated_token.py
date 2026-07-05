"""Tests for ``PaymentService.redeem_delegated_token`` (ACP money path).

The Stripe SDK is mocked at the ``stripe.PaymentIntent.create`` boundary
so these exercise *our* logic — the off-session confirm kwargs, the
idempotency key, the PaymentTransaction bookkeeping, and the never-raise
decline contract — not Stripe's network layer.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

import stripe
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.orders.models import Order
from plugins.installed.payments.models import PaymentTransaction
from plugins.installed.payments.services.stripe import PaymentService


def _order():
    return Order.objects.create(
        email='c@example.com',
        subtotal=Money(Decimal('10'), 'USD'),
        total=Money(Decimal('10'), 'USD'),
    )


class RedeemDelegatedTokenSuccessTests(TestCase):
    def test_success_records_transaction_and_sends_off_session_confirm(self):
        order = _order()
        # Evidence metadata is attached by the ACP view before redemption;
        # Order has no metadata column, so it rides as an instance attr.
        order.metadata = {'acp': {'session_id': 'sess-cart-1'}}
        intent = SimpleNamespace(id='pi_acp_1', status='succeeded')

        with mock.patch('stripe.PaymentIntent.create', return_value=intent) as create:
            result = PaymentService.redeem_delegated_token(order, 'spt_tok_1')

        create.assert_called_once()
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs['amount'], 1000)
        self.assertEqual(kwargs['currency'], 'usd')
        self.assertEqual(kwargs['payment_method'], 'spt_tok_1')
        self.assertTrue(kwargs['confirm'])
        self.assertTrue(kwargs['off_session'])
        self.assertEqual(kwargs['idempotency_key'], f'acp-{order.id}')
        self.assertEqual(
            kwargs['metadata'],
            {
                'order_id': str(order.id),
                'order_number': order.order_number,
                'acp_session': 'sess-cart-1',
            },
        )

        tx = PaymentTransaction.objects.get(order=order)
        self.assertEqual(tx.status, PaymentTransaction.Status.SUCCEEDED)
        self.assertEqual(tx.amount, order.total)
        self.assertEqual(tx.provider, 'stripe')
        self.assertEqual(tx.provider_transaction_id, 'pi_acp_1')
        self.assertEqual(
            result,
            {'success': True, 'transaction_id': tx.id, 'payment_intent_id': 'pi_acp_1'},
        )

    def test_missing_acp_metadata_sends_empty_session(self):
        order = _order()  # no metadata attr at all
        intent = SimpleNamespace(id='pi_acp_2', status='succeeded')

        with mock.patch('stripe.PaymentIntent.create', return_value=intent) as create:
            result = PaymentService.redeem_delegated_token(order, 'spt_tok_2')

        self.assertEqual(create.call_args.kwargs['metadata']['acp_session'], '')
        self.assertTrue(result['success'])


class RedeemDelegatedTokenDeclineTests(TestCase):
    def test_card_error_records_failed_tx_with_decline_code(self):
        order = _order()
        err = stripe.error.CardError(
            message='Your card was declined.', param=None, code='card_declined'
        )

        with mock.patch('stripe.PaymentIntent.create', side_effect=err):
            result = PaymentService.redeem_delegated_token(order, 'spt_declined')

        tx = PaymentTransaction.objects.get(order=order)
        self.assertEqual(tx.status, PaymentTransaction.Status.FAILED)
        self.assertEqual(tx.provider, 'stripe')
        self.assertEqual(tx.error_message, 'Your card was declined.')
        self.assertEqual(
            result,
            {
                'success': False,
                'error': 'Your card was declined.',
                'decline_code': 'card_declined',
            },
        )

    def test_generic_stripe_error_returns_failure_without_transaction(self):
        order = _order()
        err = stripe.error.APIConnectionError('Stripe is unreachable')

        with mock.patch('stripe.PaymentIntent.create', side_effect=err):
            result = PaymentService.redeem_delegated_token(order, 'spt_tok_3')

        self.assertEqual(PaymentTransaction.objects.count(), 0)
        self.assertEqual(result, {'success': False, 'error': 'Stripe is unreachable'})

    def test_non_succeeded_status_treated_as_authentication_decline(self):
        order = _order()
        intent = SimpleNamespace(id='pi_acp_3ds', status='requires_action')

        with mock.patch('stripe.PaymentIntent.create', return_value=intent):
            result = PaymentService.redeem_delegated_token(order, 'spt_needs_3ds')

        tx = PaymentTransaction.objects.get(order=order)
        self.assertEqual(tx.status, PaymentTransaction.Status.FAILED)
        self.assertEqual(tx.provider_transaction_id, 'pi_acp_3ds')
        self.assertEqual(
            result,
            {
                'success': False,
                'error': 'Payment requires additional authentication',
                'decline_code': 'authentication_required',
            },
        )

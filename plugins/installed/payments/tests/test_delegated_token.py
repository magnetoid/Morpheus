"""Tests for ``PaymentService.redeem_delegated_token`` (ACP money path).

The Stripe SDK is mocked at the ``stripe.PaymentIntent`` boundary so these
exercise *our* logic — the off-session confirm kwargs, the session-scoped
idempotency key (attempt-stable params + best-effort order linkage via
``modify``), the PaymentTransaction bookkeeping, and the never-raise
decline/retryable contract — not Stripe's network layer.
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

        with (
            mock.patch('stripe.PaymentIntent.create', return_value=intent) as create,
            mock.patch('stripe.PaymentIntent.modify') as modify,
        ):
            result = PaymentService.redeem_delegated_token(order, 'spt_tok_1')

        create.assert_called_once()
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs['amount'], 1000)
        self.assertEqual(kwargs['currency'], 'usd')
        self.assertEqual(kwargs['payment_method'], 'spt_tok_1')
        self.assertTrue(kwargs['confirm'])
        self.assertTrue(kwargs['off_session'])
        # Session-scoped, attempt-stable: a retried complete (even one that
        # re-created the pending order) must replay the SAME create request.
        self.assertEqual(kwargs['idempotency_key'], 'acp-sess-cart-1')
        self.assertEqual(kwargs['metadata'], {'acp_session': 'sess-cart-1'})
        # Order linkage is attached AFTER the idempotent create.
        modify.assert_called_once_with(
            'pi_acp_1',
            metadata={
                'acp_session': 'sess-cart-1',
                'order_id': str(order.id),
                'order_number': order.order_number,
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

    def test_missing_acp_metadata_falls_back_to_order_scoped_key(self):
        order = _order()  # no metadata attr at all
        intent = SimpleNamespace(id='pi_acp_2', status='succeeded')

        with (
            mock.patch('stripe.PaymentIntent.create', return_value=intent) as create,
            mock.patch('stripe.PaymentIntent.modify'),
            self.assertLogs('morpheus.payments.stripe', level='WARNING'),
        ):
            result = PaymentService.redeem_delegated_token(order, 'spt_tok_2')

        self.assertEqual(create.call_args.kwargs['idempotency_key'], f'acp-{order.id}')
        self.assertEqual(create.call_args.kwargs['metadata'], {'acp_session': ''})
        self.assertTrue(result['success'])

    def test_modify_failure_never_poisons_the_charge(self):
        order = _order()
        order.metadata = {'acp': {'session_id': 'sess-cart-9'}}
        intent = SimpleNamespace(id='pi_acp_9', status='succeeded')

        with (
            mock.patch('stripe.PaymentIntent.create', return_value=intent),
            mock.patch(
                'stripe.PaymentIntent.modify',
                side_effect=stripe.error.APIError('modify blew up'),
            ),
        ):
            result = PaymentService.redeem_delegated_token(order, 'spt_tok_9')

        self.assertTrue(result['success'])
        tx = PaymentTransaction.objects.get(order=order)
        self.assertEqual(tx.status, PaymentTransaction.Status.SUCCEEDED)

    def test_zero_decimal_currency_sends_whole_units(self):
        order = Order.objects.create(
            email='c@example.com',
            subtotal=Money(Decimal('1000'), 'JPY'),
            total=Money(Decimal('1000'), 'JPY'),
        )
        intent = SimpleNamespace(id='pi_jpy', status='succeeded')

        with (
            mock.patch('stripe.PaymentIntent.create', return_value=intent) as create,
            mock.patch('stripe.PaymentIntent.modify'),
        ):
            result = PaymentService.redeem_delegated_token(order, 'spt_jpy')

        self.assertTrue(result['success'])
        self.assertEqual(create.call_args.kwargs['amount'], 1000)
        self.assertEqual(create.call_args.kwargs['currency'], 'jpy')


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

    def test_card_error_without_user_message_never_leaks_str(self):
        order = _order()
        err = stripe.error.CardError(message=None, param=None, code='do_not_honor')

        with mock.patch('stripe.PaymentIntent.create', side_effect=err):
            result = PaymentService.redeem_delegated_token(order, 'spt_declined2')

        self.assertEqual(result['error'], 'Payment was declined.')
        self.assertEqual(result['decline_code'], 'do_not_honor')
        tx = PaymentTransaction.objects.get(order=order)
        self.assertEqual(tx.error_message, 'Payment was declined.')

    def test_connection_error_is_retryable_with_no_transaction_row(self):
        order = _order()
        err = stripe.error.APIConnectionError('Stripe is unreachable')

        with mock.patch('stripe.PaymentIntent.create', side_effect=err):
            result = PaymentService.redeem_delegated_token(order, 'spt_tok_3')

        # Ambiguous outcome — no intent id is known, so no transaction row;
        # the caller retries the same session (replay-safe idempotency key).
        self.assertEqual(PaymentTransaction.objects.count(), 0)
        self.assertEqual(
            result,
            {
                'success': False,
                'error': 'Payment processing was interrupted — retry this completion.',
                'retryable': True,
            },
        )

    def test_generic_stripe_error_returns_fixed_message_and_logs_raw(self):
        order = _order()
        err = stripe.error.APIError('internal stripe details: sk_live_wouldleak')

        with (
            mock.patch('stripe.PaymentIntent.create', side_effect=err),
            self.assertLogs('morpheus.payments.stripe', level='ERROR') as logs,
        ):
            result = PaymentService.redeem_delegated_token(order, 'spt_tok_4')

        self.assertEqual(PaymentTransaction.objects.count(), 0)
        self.assertEqual(result, {'success': False, 'error': 'Payment could not be processed.'})
        self.assertIn('internal stripe details', '\n'.join(logs.output))

    def test_processing_intent_records_pending_and_is_retryable(self):
        order = _order()
        intent = SimpleNamespace(id='pi_proc_1', status='processing')

        with (
            mock.patch('stripe.PaymentIntent.create', return_value=intent),
            mock.patch('stripe.PaymentIntent.modify'),
        ):
            result = PaymentService.redeem_delegated_token(order, 'spt_processing')

        # PENDING (not FAILED) — the payment_intent.succeeded webhook
        # promotes this row when the asynchronous charge settles.
        tx = PaymentTransaction.objects.get(order=order)
        self.assertEqual(tx.status, PaymentTransaction.Status.PENDING)
        self.assertEqual(tx.provider_transaction_id, 'pi_proc_1')
        self.assertEqual(
            result,
            {
                'success': False,
                'error': 'Payment is processing.',
                'decline_code': 'processing',
                'retryable': True,
            },
        )

    def test_non_succeeded_status_treated_as_authentication_decline(self):
        order = _order()
        intent = SimpleNamespace(id='pi_acp_3ds', status='requires_action')

        with (
            mock.patch('stripe.PaymentIntent.create', return_value=intent),
            mock.patch('stripe.PaymentIntent.modify'),
        ):
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

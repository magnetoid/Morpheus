"""Webhook-processing tests for ``PaymentService.process_webhook``.

The Stripe SDK is mocked at the ``construct_event`` boundary so these
exercise *our* logic — signature rejection, event-id idempotency, the
transaction/order state advance, and the exactly-once ORDER_PAID fire —
not Stripe's HMAC implementation.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

import stripe
from django.test import TestCase
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.orders.models import Order
from plugins.installed.payments.models import PaymentTransaction, StripeWebhookEvent
from plugins.installed.payments.services.stripe import PaymentService


class FakeEvent:
    """Stands in for stripe.Event: just the attributes process_webhook reads."""

    def __init__(self, event_id, event_type, intent_id, error_msg=''):
        self.id = event_id
        self.type = event_type
        self.data = SimpleNamespace(
            object=SimpleNamespace(
                id=intent_id,
                last_payment_error=SimpleNamespace(message=error_msg),
            )
        )

    def to_dict(self):
        return {'id': self.id, 'type': self.type}


def _order_with_tx(intent_id='pi_test_1'):
    order = Order.objects.create(
        email='c@example.com',
        subtotal=Money(Decimal('10'), 'USD'),
        total=Money(Decimal('10'), 'USD'),
    )
    tx = PaymentTransaction.objects.create(
        order=order,
        amount=order.total,
        provider='stripe',
        provider_transaction_id=intent_id,
    )
    return order, tx


def _deliver(event):
    """Run process_webhook with construct_event mocked to return `event`."""
    with mock.patch('stripe.Webhook.construct_event', return_value=event):
        return PaymentService.process_webhook(b'{}', 'sig')


class WebhookSignatureTests(TestCase):
    def test_invalid_signature_rejected_before_any_write(self):
        err = stripe.error.SignatureVerificationError('bad sig', 'sig_header')
        with (
            mock.patch('stripe.Webhook.construct_event', side_effect=err),
            self.assertRaisesMessage(Exception, 'Invalid signature'),
        ):
            PaymentService.process_webhook(b'{}', 'sig')
        self.assertEqual(StripeWebhookEvent.objects.count(), 0)

    def test_invalid_payload_rejected(self):
        with (
            mock.patch('stripe.Webhook.construct_event', side_effect=ValueError('nope')),
            self.assertRaisesMessage(Exception, 'Invalid payload'),
        ):
            PaymentService.process_webhook(b'{}', 'sig')
        self.assertEqual(StripeWebhookEvent.objects.count(), 0)


class PaymentSucceededTests(TestCase):
    def setUp(self):
        self.paid_orders = []
        self._listener = lambda order, **kw: self.paid_orders.append(order)
        hook_registry.register(MorpheusEvents.ORDER_PAID, self._listener)
        self.addCleanup(hook_registry.unregister, MorpheusEvents.ORDER_PAID, self._listener)

    def test_succeeded_advances_tx_and_order(self):
        order, tx = _order_with_tx()
        _deliver(FakeEvent('evt_1', 'payment_intent.succeeded', tx.provider_transaction_id))

        tx.refresh_from_db()
        order = Order.objects.get(pk=order.pk)
        self.assertEqual(tx.status, PaymentTransaction.Status.SUCCEEDED)
        self.assertEqual(order.payment_status, 'paid')
        self.assertEqual(order.status, 'confirmed')
        self.assertEqual([o.pk for o in self.paid_orders], [order.pk])

        row = StripeWebhookEvent.objects.get(stripe_event_id='evt_1')
        self.assertTrue(row.is_processed)
        self.assertIsNotNone(row.processed_at)

    def test_retry_with_same_event_id_is_a_noop(self):
        order, tx = _order_with_tx()
        event = FakeEvent('evt_dup', 'payment_intent.succeeded', tx.provider_transaction_id)
        self.assertTrue(_deliver(event))
        self.assertTrue(_deliver(event))  # Stripe redelivery → swallowed

        self.assertEqual(StripeWebhookEvent.objects.count(), 1)
        self.assertEqual(len(self.paid_orders), 1)

    def test_second_event_for_same_intent_fires_order_paid_once(self):
        order, tx = _order_with_tx()
        _deliver(FakeEvent('evt_a', 'payment_intent.succeeded', tx.provider_transaction_id))
        _deliver(FakeEvent('evt_b', 'payment_intent.succeeded', tx.provider_transaction_id))

        self.assertEqual(len(self.paid_orders), 1)
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.SUCCEEDED)

    def test_already_processing_order_only_flips_payment_status(self):
        order, tx = _order_with_tx()
        order.confirm()
        order.process()
        order.save()

        _deliver(FakeEvent('evt_p', 'payment_intent.succeeded', tx.provider_transaction_id))
        order = Order.objects.get(pk=order.pk)
        self.assertEqual(order.status, 'processing')
        self.assertEqual(order.payment_status, 'paid')

    def test_unknown_intent_is_recorded_but_changes_nothing(self):
        order, tx = _order_with_tx()
        _deliver(FakeEvent('evt_x', 'payment_intent.succeeded', 'pi_unknown'))

        tx.refresh_from_db()
        order = Order.objects.get(pk=order.pk)
        self.assertEqual(tx.status, PaymentTransaction.Status.PENDING)
        self.assertEqual(order.payment_status, 'unpaid')
        self.assertEqual(self.paid_orders, [])
        self.assertTrue(StripeWebhookEvent.objects.get(stripe_event_id='evt_x').is_processed)

    def test_handler_failure_is_recorded_and_reraised_for_retry(self):
        order, tx = _order_with_tx()
        boom = RuntimeError('db went away')
        with (
            mock.patch.object(PaymentService, '_mark_transaction_success', side_effect=boom),
            self.assertRaises(RuntimeError),
        ):
            _deliver(FakeEvent('evt_err', 'payment_intent.succeeded', tx.provider_transaction_id))

        row = StripeWebhookEvent.objects.get(stripe_event_id='evt_err')
        self.assertFalse(row.is_processed)
        self.assertIn('db went away', row.error)


class PaymentFailedTests(TestCase):
    def test_failed_marks_tx_with_error(self):
        order, tx = _order_with_tx()
        _deliver(
            FakeEvent(
                'evt_f',
                'payment_intent.payment_failed',
                tx.provider_transaction_id,
                error_msg='card_declined',
            )
        )
        tx.refresh_from_db()
        order = Order.objects.get(pk=order.pk)
        self.assertEqual(tx.status, PaymentTransaction.Status.FAILED)
        self.assertEqual(tx.error_message, 'card_declined')
        self.assertEqual(order.payment_status, 'unpaid')

    def test_failed_event_cannot_overwrite_a_success(self):
        order, tx = _order_with_tx()
        _deliver(FakeEvent('evt_ok', 'payment_intent.succeeded', tx.provider_transaction_id))
        _deliver(
            FakeEvent(
                'evt_late_fail',
                'payment_intent.payment_failed',
                tx.provider_transaction_id,
                error_msg='stale retry',
            )
        )
        tx.refresh_from_db()
        self.assertEqual(tx.status, PaymentTransaction.Status.SUCCEEDED)
        self.assertEqual(tx.error_message, '')

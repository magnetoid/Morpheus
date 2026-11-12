"""PAYMENT_FAILED has a producer and a subscriber (v0.155.0).

Until v0.155.0 the event was declared and nothing fired it, so a declined card
left an unpaid order with nothing on its timeline to say why.
"""

from __future__ import annotations

from django.test import TestCase
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.orders.models import Order
from plugins.installed.payments.models import PaymentTransaction
from plugins.installed.payments.services.stripe import PaymentService

Status = PaymentTransaction.Status


class PaymentFailedEventTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            email='decline@example.com', subtotal=Money(9, 'USD'), total=Money(9, 'USD')
        )
        self.tx = PaymentTransaction.objects.create(
            order=self.order,
            amount=self.order.total,
            provider='stripe',
            provider_transaction_id='pi_declined',
        )
        self.seen = []

        def listen(**kwargs):
            self.seen.append(kwargs)

        hook_registry.register(MorpheusEvents.PAYMENT_FAILED, listen, plugin=None)
        self.addCleanup(hook_registry.unregister, MorpheusEvents.PAYMENT_FAILED, listen)

    def test_a_declined_card_fires_once_and_goes_on_the_timeline(self):
        PaymentService._mark_transaction_failed('pi_declined', 'Your card was declined.')
        PaymentService._mark_transaction_failed('pi_declined', 'Insufficient funds.')
        self.assertEqual(len(self.seen), 1)
        self.assertEqual(self.seen[0]['error'], 'Your card was declined.')
        self.assertEqual(self.seen[0]['order'].pk, self.order.pk)
        events = self.order.events.filter(event_type='PAYMENT_FAILED')
        self.assertEqual(
            list(events.values_list('message', flat=True)), ['Your card was declined.']
        )
        self.tx.refresh_from_db()
        self.assertEqual(
            (self.tx.status, self.tx.error_message), (Status.FAILED, 'Insufficient funds.')
        )

    def test_a_late_failure_never_touches_a_taken_payment(self):
        PaymentTransaction.objects.filter(pk=self.tx.pk).update(status=Status.SUCCEEDED)
        PaymentService._mark_transaction_failed('pi_declined', 'late')
        self.assertEqual(self.seen, [])
        self.assertFalse(self.order.events.filter(event_type='PAYMENT_FAILED').exists())

    def test_a_key_in_the_reason_is_not_stored(self):
        PaymentService._mark_transaction_failed(
            'pi_declined', 'Invalid API Key provided: sk_live_' + 'a' * 24
        )
        message = self.order.events.get(event_type='PAYMENT_FAILED').message
        self.assertNotIn('sk_live_' + 'a' * 24, message)

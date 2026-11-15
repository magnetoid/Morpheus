"""An order waiting for its payment link outlives the unpaid-order sweep (A8).

The sweep cancels a ``pending`` order nobody paid within the expiry window. A
draft converted by staff has no gateway, so it was cancelled an hour later and
its stock released, before any customer could pay it. An order carrying
``metadata['pay_by']`` now keeps until then.
"""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from core.hooks import MorpheusEvents, hook_registry
from plugins.installed.orders import payment_deadline
from plugins.installed.orders.models import Order
from plugins.installed.orders.tasks import expire_pending_orders
from plugins.testing import set_app_settings


def _stale_order(**metadata):
    order = Order.objects.create(
        email='later@example.com', subtotal=Money(5, 'USD'), total=Money(5, 'USD')
    )
    Order.objects.filter(pk=order.pk).update(
        placed_at=timezone.now() - timedelta(hours=5), metadata=metadata
    )
    return Order.objects.get(pk=order.pk)


def _status(order):
    return Order.objects.values_list('status', flat=True).get(pk=order.pk)


class SweepKeepsHeldOrdersTests(TestCase):
    def test_a_deadline_ahead_keeps_the_order(self):
        ahead = (timezone.now() + timedelta(hours=1)).isoformat()
        order = _stale_order(pay_by=ahead)
        self.assertEqual(expire_pending_orders(), 0)
        self.assertEqual(_status(order), 'pending')

    def test_no_deadline_keeps_the_order(self):
        order = _stale_order(pay_by=None)
        self.assertEqual(expire_pending_orders(), 0)
        self.assertEqual(_status(order), 'pending')

    def test_a_passed_deadline_cancels_and_says_why(self):
        passed = (timezone.now() - timedelta(minutes=1)).isoformat()
        order = _stale_order(pay_by=passed)
        self.assertEqual(expire_pending_orders(), 1)
        self.assertEqual(_status(order), 'cancelled')
        notes = Order.objects.values_list('staff_notes', flat=True).get(pk=order.pk)
        self.assertIn('payment link expired', notes)

    def test_an_ordinary_order_still_expires(self):
        order = _stale_order()
        self.assertEqual(expire_pending_orders(), 1)
        self.assertEqual(_status(order), 'cancelled')


class HoldForPaymentTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            email='later@example.com', subtotal=Money(5, 'USD'), total=Money(5, 'USD')
        )

    def stored(self):
        return Order.objects.values_list('metadata', flat=True).get(pk=self.order.pk)

    def test_the_setting_sets_the_deadline(self):
        set_app_settings(self, 'orders', payment_link_hours=24)
        deadline = payment_deadline.hold_for_payment(self.order, reason='link')
        self.assertAlmostEqual(
            deadline.timestamp(), (timezone.now() + timedelta(hours=24)).timestamp(), delta=60
        )
        self.assertEqual(self.stored()['pay_by'], deadline.isoformat())
        self.assertTrue(payment_deadline.waiting_for_payment(self.order))

    def test_zero_hours_means_no_deadline(self):
        set_app_settings(self, 'orders', payment_link_hours=0)
        self.assertIsNone(payment_deadline.hold_for_payment(self.order, reason='draft'))
        self.assertIn('pay_by', self.stored())
        self.assertIsNone(self.stored()['pay_by'])

    def test_a_later_deadline_is_never_shortened(self):
        set_app_settings(self, 'orders', payment_link_hours=72)
        first = payment_deadline.hold_for_payment(self.order, reason='draft')
        set_app_settings(self, 'orders', payment_link_hours=1)
        self.assertEqual(payment_deadline.hold_for_payment(self.order, reason='link'), first)
        self.assertEqual(self.stored()['pay_by'], first.isoformat())

    def test_an_app_can_set_the_deadline(self):
        chosen = timezone.now() + timedelta(days=30)

        def thirty_days(value, order=None, reason='', **kwargs):
            return chosen if reason == 'link' else value

        hook_registry.register(MorpheusEvents.PAYMENT_LINK_DEADLINE, thirty_days, plugin=None)
        self.addCleanup(hook_registry.unregister, MorpheusEvents.PAYMENT_LINK_DEADLINE, thirty_days)
        self.assertEqual(payment_deadline.hold_for_payment(self.order, reason='link'), chosen)

    def test_the_customer_is_told_only_a_deadline_the_sweep_keeps(self):
        payment_deadline.hold_for_payment(self.order, reason='link')
        self.assertIsNotNone(payment_deadline.cancels_at(self.order))
        set_app_settings(self, 'orders', pending_order_expiry_minutes=0)
        self.assertIsNone(payment_deadline.cancels_at(self.order))

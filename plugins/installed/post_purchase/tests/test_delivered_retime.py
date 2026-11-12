"""Follow-ups count from the delivery once the order is delivered.

Shipping starts the clock as a guess; ORDER_DELIVERED (orders' FSM signal since
v0.154.0) re-times every step still queued, and leaves one that went out.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money


class DeliveredRetimeTests(TestCase):
    def setUp(self):
        from plugins.installed.orders.models import Order

        self.order = Order.objects.create(
            email='b@example.com',
            subtotal=Money(10, 'USD'),
            total=Money(10, 'USD'),
            status='shipped',
            payment_status='paid',
        )

    def test_delivery_moves_queued_steps_and_keeps_sent_ones(self):
        from plugins.installed.post_purchase.handlers import on_order_fulfilled
        from plugins.installed.post_purchase.models import JourneyStep

        on_order_fulfilled(order=self.order)
        long_ago = timezone.now() - timedelta(days=5)
        JourneyStep.objects.filter(order=self.order).update(due_at=long_ago)
        JourneyStep.objects.filter(order=self.order, step='nps_survey').update(status='sent')

        with self.captureOnCommitCallbacks(execute=True):
            self.order.deliver()
            self.order.save()

        steps = {s.step: s for s in JourneyStep.objects.filter(order=self.order)}
        self.assertGreater(steps['delivered_followup'].due_at, timezone.now())
        self.assertGreater(steps['review_request'].due_at, timezone.now() + timedelta(days=13))
        self.assertEqual(steps['nps_survey'].due_at, long_ago)

    def test_delivery_without_shipping_events_still_schedules(self):
        from plugins.installed.post_purchase.handlers import on_order_delivered
        from plugins.installed.post_purchase.models import JourneyStep

        on_order_delivered(order=self.order)
        self.assertEqual(
            set(JourneyStep.objects.filter(order=self.order).values_list('step', flat=True)),
            {'delivered_followup', 'review_request', 'nps_survey'},
        )

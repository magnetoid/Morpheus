"""A refund made outside the store is recorded through the refund path.

`orders.mark_refunded` (Linda's tool) and the `markOrderRefunded` mutation set
`status='refunded'` with a queryset `update()`: no Refund row, no FSM transition
and no PAYMENT_REFUNDED, so a gift card or points spent on the order were never
re-credited and no refund email went out (found 2026-10-12). Both now go through
`RefundService.record_external`, which records the rest of the order total as a
processed refund without calling a gateway.
"""

from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.test import TestCase
from djmoney.money import Money

from core.agents.tools import ToolError
from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.orders.models import Order, Refund
from plugins.installed.orders.refunds import RefundService


def _usd(n):
    return Money(Decimal(str(n)), 'USD')


class RecordExternalRefundTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(email='c@example.com', subtotal=_usd(50), total=_usd(50))
        self.fired = []
        real_fire = hook_registry.fire

        def spy(event, *args, **kwargs):
            if event == MorpheusEvents.PAYMENT_REFUNDED:
                self.fired.append(kwargs)
            return real_fire(event, *args, **kwargs)

        patcher = mock.patch.object(hook_registry, 'fire', side_effect=spy)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_remaining_total_is_recorded_as_a_processed_refund(self):
        RefundService.record_external(order=self.order, notes='Refunded in Stripe')
        refund = Refund.objects.get(order=self.order)
        self.assertTrue(refund.is_processed)
        self.assertEqual(refund.amount, _usd(50))
        self.assertEqual(Order.objects.get(pk=self.order.pk).status, 'refunded')
        self.assertEqual(len(self.fired), 1)
        self.assertEqual(self.fired[0]['amount'], _usd(50))

    def test_only_what_is_left_after_earlier_refunds(self):
        Refund.objects.create(order=self.order, amount=_usd(20), is_processed=True)
        RefundService.record_external(order=self.order)
        self.assertEqual(
            Refund.objects.filter(order=self.order).latest('created_at').amount, _usd(30)
        )

    def test_nothing_left_to_refund_is_an_error(self):
        RefundService.record_external(order=self.order)
        with self.assertRaises(ValueError):
            RefundService.record_external(order=self.order)
        self.assertEqual(len(self.fired), 1)

    def test_lindas_tool_takes_the_refund_path(self):
        from core.agents import agent_registry

        tool = agent_registry.get_tool('orders.mark_refunded')
        tool.invoke({'order_number': self.order.order_number, 'reason': 'Refunded by phone'})
        self.assertTrue(Refund.objects.get(order=self.order).is_processed)
        self.assertEqual(len(self.fired), 1)
        with self.assertRaises(ToolError):
            tool.invoke({'order_number': self.order.order_number})

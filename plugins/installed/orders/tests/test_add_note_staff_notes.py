"""Notes from Linda and from workflows land in the order's staff notes (A8).

``orders.add_note`` and the workflows action ``add_order_note`` wrote
``Order.notes``, a field Order does not have, so both failed every time.
"""

from __future__ import annotations

from django.test import TestCase
from djmoney.money import Money

from core.agents import agent_registry
from plugins.installed.orders.models import Order
from plugins.installed.workflows.engine import _action_add_order_note


class StaffNotesTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            email='notes@example.com',
            subtotal=Money(5, 'USD'),
            total=Money(5, 'USD'),
            staff_notes='Called the customer.',
        )

    def notes(self):
        return Order.objects.values_list('staff_notes', flat=True).get(pk=self.order.pk)

    def test_linda_appends_a_note(self):
        tool = agent_registry.get_tool('orders.add_note')
        tool.handler(order_number=self.order.order_number, note='Ships Friday.', confirmed=True)
        self.assertEqual(self.notes(), 'Called the customer.\n\nShips Friday.')

    def test_a_workflow_appends_a_note(self):
        ok, detail = _action_add_order_note({'note': 'VIP'}, {'order': self.order})
        self.assertTrue(ok, detail)
        self.assertEqual(self.notes(), 'Called the customer.\n\nVIP')

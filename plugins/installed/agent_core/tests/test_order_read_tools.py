"""agent_core's order/revenue read tools must run against the real Order model.

`orders.list_recent`, `orders.summary` and `analytics.revenue_summary` read
`Order.state` and `Order.created_at`, neither of which exists (the model has
`status`, `payment_status` and `placed_at`), so all three raised on every call
and the agent could not answer "what are my recent orders?" or "what did I
make this month?". Found by invoking every registered tool.
"""

from __future__ import annotations

from django.test import TestCase
from djmoney.money import Money

from morpheus.core import agent_registry


def _invoke(name, args):
    return agent_registry.get_tool(name).invoke(args, agent=None, context={'source': 'mcp'})


class OrderReadToolTests(TestCase):
    def setUp(self):
        from plugins.installed.orders.models import Order

        self.paid = Order.objects.create(
            email='paid@example.com', subtotal=Money(30, 'USD'), total=Money(30, 'USD')
        )
        Order.objects.filter(pk=self.paid.pk).update(payment_status='paid')
        self.unpaid = Order.objects.create(
            email='unpaid@example.com', subtotal=Money(5, 'USD'), total=Money(5, 'USD')
        )

    def test_list_recent_lists_orders_newest_first(self):
        rows = _invoke('orders.list_recent', {}).output['orders']
        self.assertEqual(
            [r['order_number'] for r in rows],
            [self.unpaid.order_number, self.paid.order_number],
        )
        self.assertEqual(rows[0]['state'], 'pending')

    def test_list_recent_filters_by_status(self):
        rows = _invoke('orders.list_recent', {'state': 'cancelled'}).output['orders']
        self.assertEqual(rows, [])

    def test_summary_describes_one_order(self):
        out = _invoke('orders.summary', {'order_number': self.paid.order_number}).output
        self.assertEqual(out['order_number'], self.paid.order_number)
        self.assertEqual(out['state'], 'pending')
        self.assertTrue(out['created_at'])

    def test_revenue_counts_paid_orders_only(self):
        out = _invoke('analytics.revenue_summary', {'days': 30}).output
        self.assertEqual(out['order_count'], 1)
        self.assertEqual(out['revenue'], '30.00')

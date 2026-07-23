"""Max refund-value guardrail on orders.refund.

The per-action cap (Settings → Agent guardrails) refuses an agent refund above
it — checked on the RESOLVED amount (order.total on a full refund) after the
hard gate but before the payment provider is charged. 0/unset = no cap.
"""

from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from core.agents.tools import ToolError
from plugins.installed.orders.agent_tools import refund_order_tool
from plugins.installed.orders.models import Order

User = get_user_model()


def _order(total='50'):
    user = User.objects.create_user(username='c', email='c@example.com', password='x')
    return Order.objects.create(
        customer=user,
        email='c@example.com',
        subtotal=Money(Decimal(total), 'USD'),
        total=Money(Decimal(total), 'USD'),
    )


class RefundCapTests(TestCase):
    def test_full_refund_over_cap_is_refused_before_charging(self):
        order = _order('50')  # full refund would be $50
        with (
            mock.patch('plugins.installed.orders.agent_tools.max_refund_value', return_value=10),
            mock.patch(
                'plugins.installed.orders.refunds.RefundService.process',
                side_effect=AssertionError('must not charge on a capped refund'),
            ),
            self.assertRaises(ToolError) as ctx,
        ):
            refund_order_tool.invoke(
                {
                    'order_number': order.order_number,
                    'confirmed': True,
                    'hard_gate_ack': 'YES',
                    'echo': order.order_number,
                }
            )
        self.assertIn('exceeds', str(ctx.exception))

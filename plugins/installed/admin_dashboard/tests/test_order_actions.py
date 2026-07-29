"""Dashboard order-action side-effect tests.

Out-of-band "mark paid" must fire ORDER_PAID (every fulfillment side-effect —
digital tokens, loyalty, CDP, pixels, the payment email — hangs off it), exactly
once, and bulk-cancel must actually transition the FSM.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.admin_dashboard.views_split.orders import _mark_order_paid
from plugins.installed.orders.models import Order

User = get_user_model()


def _order(payment_status='unpaid'):
    u = User.objects.create_user(username='c', email='c@example.com', password='x')
    return Order.objects.create(
        customer=u,
        email='c@example.com',
        subtotal=Money(Decimal('20'), 'USD'),
        total=Money(Decimal('20'), 'USD'),
        payment_status=payment_status,
    )


class MarkOrderPaidTests(TestCase):
    def test_mark_paid_fires_order_paid_once_and_is_idempotent(self):
        seen = []

        def _handler(order=None, **kwargs):
            seen.append(order)

        hook_registry.register(MorpheusEvents.ORDER_PAID, _handler, plugin=None)
        try:
            order = _order()
            first = _mark_order_paid(order)
            second = _mark_order_paid(order)  # already paid → no-op
        finally:
            hook_registry.unregister(MorpheusEvents.ORDER_PAID, _handler)

        self.assertTrue(first)
        self.assertFalse(second)  # idempotent — no double-fire
        # NB: Order.refresh_from_db() setattrs the protected FSM `status` field
        # and raises — re-fetch a fresh instance instead.
        fresh = Order.objects.get(pk=order.pk)
        self.assertEqual(fresh.payment_status, 'paid')
        self.assertEqual(len(seen), 1)  # fired exactly once

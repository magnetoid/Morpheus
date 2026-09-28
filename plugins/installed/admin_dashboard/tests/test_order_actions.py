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


class MarkPaidConfirmsTests(TestCase):
    """A cash or bank-transfer order marked paid is confirmed, like an online
    payment; left 'pending' it dropped out of every paid-order count."""

    def test_mark_paid_confirms_a_pending_order(self):
        order = _order()
        _mark_order_paid(order)
        fresh = Order.objects.get(pk=order.pk)
        self.assertEqual((fresh.payment_status, fresh.status), ('paid', 'confirmed'))

    def test_mark_paid_leaves_a_shipped_order_shipped(self):
        order = _order()
        Order.objects.filter(pk=order.pk).update(status='shipped')
        _mark_order_paid(Order.objects.get(pk=order.pk))
        fresh = Order.objects.get(pk=order.pk)
        self.assertEqual((fresh.payment_status, fresh.status), ('paid', 'shipped'))


class AwaitingPaymentListTests(TestCase):
    """Delivered cash-on-delivery orders nobody marked paid are called out."""

    def setUp(self):
        staff = User.objects.create_user(
            username='staff', email='staff@example.com', password='x', is_staff=True
        )
        self.client.force_login(staff)
        self.waiting = _order()
        Order.objects.filter(pk=self.waiting.pk).update(status='delivered', payment_gateway='cod')
        paid = Order.objects.create(
            email='p@example.com',
            subtotal=Money(Decimal('5'), 'USD'),
            total=Money(Decimal('5'), 'USD'),
            payment_status='paid',
            payment_gateway='cod',
        )
        Order.objects.filter(pk=paid.pk).update(status='delivered')
        self.paid = paid

    def test_the_list_says_how_many_are_waiting(self):
        body = self.client.get('/dashboard/orders/').content.decode()
        self.assertIn('1 shipped or delivered order paid by cash or bank transfer is not', body)

    def test_the_filter_shows_only_those_orders(self):
        body = self.client.get('/dashboard/orders/?awaiting_payment=1').content.decode()
        self.assertIn(self.waiting.order_number, body)
        self.assertNotIn(self.paid.order_number, body)

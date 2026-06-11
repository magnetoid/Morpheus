"""Order FSM state-machine tests.

``Order.status`` is a protected FSMField: every transition must go
through the decorated methods, each of which appends an immutable
``OrderEvent``. These tests pin the legal transition graph, the event
trail, and the guard against direct status writes.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from django_fsm import TransitionNotAllowed
from djmoney.money import Money

from plugins.installed.orders.models import Order, OrderEvent


def _order():
    return Order.objects.create(
        email='c@example.com',
        subtotal=Money(Decimal('10'), 'USD'),
        total=Money(Decimal('10'), 'USD'),
    )


class HappyPathTests(TestCase):
    def test_full_lifecycle(self):
        order = _order()
        self.assertEqual(order.status, 'pending')

        order.confirm()
        self.assertEqual(order.status, 'confirmed')
        order.process()
        self.assertEqual(order.status, 'processing')
        order.fulfill()
        self.assertEqual(order.status, 'fulfilled')
        order.ship(tracking_number='TRACK123')
        self.assertEqual(order.status, 'shipped')
        self.assertEqual(order.tracking_number, 'TRACK123')
        order.deliver()
        self.assertEqual(order.status, 'delivered')

        events = list(
            OrderEvent.objects.filter(order=order)
            .order_by('created_at')
            .values_list('event_type', 'previous_state', 'new_state')
        )
        self.assertEqual(
            events,
            [
                ('ORDER_CONFIRMED', 'pending', 'confirmed'),
                ('ORDER_PROCESSING', 'confirmed', 'processing'),
                ('ORDER_FULFILLED', 'processing', 'fulfilled'),
                ('ORDER_SHIPPED', 'fulfilled', 'shipped'),
                ('ORDER_DELIVERED', 'shipped', 'delivered'),
            ],
        )

    def test_ship_straight_from_processing(self):
        order = _order()
        order.confirm()
        order.process()
        order.ship()
        self.assertEqual(order.status, 'shipped')
        self.assertEqual(order.tracking_number, '')

    def test_fulfill_from_partially_fulfilled(self):
        order = _order()
        # No FSM transition targets partially_fulfilled — the fulfillment
        # service sets it via a queryset update — so mirror that here.
        Order.objects.filter(pk=order.pk).update(status='partially_fulfilled')
        order = Order.objects.get(pk=order.pk)
        order.fulfill()
        self.assertEqual(order.status, 'fulfilled')


class IllegalTransitionTests(TestCase):
    def test_cannot_skip_confirm(self):
        order = _order()
        with self.assertRaises(TransitionNotAllowed):
            order.process()

    def test_cannot_ship_a_pending_order(self):
        order = _order()
        with self.assertRaises(TransitionNotAllowed):
            order.ship()

    def test_cannot_deliver_before_shipping(self):
        order = _order()
        order.confirm()
        with self.assertRaises(TransitionNotAllowed):
            order.deliver()

    def test_cannot_confirm_twice(self):
        order = _order()
        order.confirm()
        with self.assertRaises(TransitionNotAllowed):
            order.confirm()

    def test_direct_status_assignment_is_blocked(self):
        order = _order()
        with self.assertRaises(AttributeError):
            order.status = 'shipped'


class CancelTests(TestCase):
    def test_cancel_from_pending(self):
        order = _order()
        order.cancel(reason='customer changed mind')
        self.assertEqual(order.status, 'cancelled')
        self.assertIsNotNone(order.cancelled_at)
        self.assertIn('customer changed mind', order.staff_notes)

        event = OrderEvent.objects.get(order=order, event_type='ORDER_CANCELLED')
        self.assertEqual(event.previous_state, 'pending')
        self.assertEqual(event.message, 'customer changed mind')

    def test_cancel_from_shipped(self):
        order = _order()
        order.confirm()
        order.process()
        order.ship()
        order.cancel()
        self.assertEqual(order.status, 'cancelled')

    def test_transitions_blocked_after_cancel(self):
        order = _order()
        order.cancel()
        with self.assertRaises(TransitionNotAllowed):
            order.confirm()

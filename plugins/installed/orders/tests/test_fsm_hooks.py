"""Order FSM transitions fire the platform hooks (regression for the dead
ORDER_FULFILLED / ORDER_CANCELLED events).

Before the post_transition wiring, these events had subscribers (shipment +
cancellation emails, stock release, affiliate clawback) but no fire site, so
the side-effects silently never ran. These tests assert the hook fires from
whatever call site runs the transition — the whole point of centralizing it.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.orders.models import Order


def _order(status='pending'):
    o = Order.objects.create(
        email='c@example.com',
        subtotal=Money(Decimal('10'), 'USD'),
        total=Money(Decimal('10'), 'USD'),
    )
    if status != 'pending':
        Order.objects.filter(pk=o.pk).update(status=status)
        o = Order.objects.get(pk=o.pk)  # re-fetch — FSM blocks refresh_from_db on status
    return o


class _Capture:
    def __init__(self, event):
        self.event = event
        self.calls = []

    def __enter__(self):
        hook_registry.register(self.event, self._handler, plugin=None)
        return self

    def __exit__(self, *a):
        hook_registry.unregister(self.event, self._handler)

    def _handler(self, order=None, **kwargs):
        self.calls.append(order)


class OrderFsmHookTests(TestCase):
    def test_fulfill_fires_order_fulfilled(self):
        order = _order('processing')
        with _Capture(MorpheusEvents.ORDER_FULFILLED) as cap:
            order.fulfill()
            order.save()
        self.assertEqual(len(cap.calls), 1)
        self.assertEqual(cap.calls[0].pk, order.pk)

    def test_cancel_fires_order_cancelled(self):
        order = _order('confirmed')
        with _Capture(MorpheusEvents.ORDER_CANCELLED) as cap:
            order.cancel(reason='test')
            order.save()
        self.assertEqual(len(cap.calls), 1)
        self.assertEqual(cap.calls[0].pk, order.pk)

    def test_confirm_does_not_fire_fulfilled_or_cancelled(self):
        order = _order('pending')
        with (
            _Capture(MorpheusEvents.ORDER_FULFILLED) as fulf,
            _Capture(MorpheusEvents.ORDER_CANCELLED) as canc,
        ):
            order.confirm()
            order.save()
        self.assertEqual(fulf.calls, [])
        self.assertEqual(canc.calls, [])

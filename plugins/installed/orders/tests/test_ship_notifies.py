"""Shipping an order tells the customer it is on its way.

The dashboard's fulfil form ships straight from 'processing', skipping the
'fulfilled' state — the only one that fired ORDER_FULFILLED. So the "on its
way" email (with the tracking number), post-purchase follow-ups and merchant
webhooks never happened for any shipped order. Fulfilment now fires on
whichever of the two states the order reaches first, and only once.
"""

from __future__ import annotations

from decimal import Decimal

from django.core import mail
from django.test import TestCase, override_settings
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.orders.models import Order


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='shop@example.com',
)
class ShippingNotifiesTests(TestCase):
    def _order(self):
        order = Order.objects.create(
            email='buyer@example.com',
            subtotal=Money(Decimal('8.00'), 'USD'),
            total=Money(Decimal('8.00'), 'USD'),
        )
        Order.objects.filter(pk=order.pk).update(status='processing')
        return Order.objects.get(pk=order.pk)

    def _fulfilment_events(self, steps):
        seen = []

        def handler(order=None, **kwargs):
            seen.append(order.pk)

        hook_registry.register(MorpheusEvents.ORDER_FULFILLED, handler, plugin=None)
        self.addCleanup(hook_registry.unregister, MorpheusEvents.ORDER_FULFILLED, handler)
        with self.captureOnCommitCallbacks(execute=True):
            steps()
        return seen

    def _on_its_way(self):
        return [m for m in mail.outbox if 'is on its way' in m.subject]

    def test_shipping_from_processing_tells_the_customer(self):
        order = self._order()

        def steps():
            order.ship(tracking_number='TRACK123')
            order.save()

        self.assertEqual(len(self._fulfilment_events(steps)), 1)
        emails = self._on_its_way()
        self.assertEqual(len(emails), 1)
        self.assertIn('TRACK123', emails[0].body)
        self.assertEqual(emails[0].to, ['buyer@example.com'])

    def test_fulfilled_then_shipped_tells_them_once(self):
        order = self._order()

        def steps():
            order.fulfill()
            order.save()
            order.ship(tracking_number='TRACK456')
            order.save()

        self.assertEqual(len(self._fulfilment_events(steps)), 1)
        self.assertEqual(len(self._on_its_way()), 1)

"""A double-clicked refund refunds once.

The dashboard's refund form created its Refund row directly and fired the
gateway hook itself, bypassing RefundService — so every click made its own row
with its own gateway idempotency key, and could refund the customer twice. It
now goes through RefundService, which reuses an identical pending row and locks
the order against concurrent clicks.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.admin_dashboard.forms.orders import RefundForm
from plugins.installed.orders.models import Order


class RefundFormTests(TestCase):
    def test_submitting_the_same_refund_twice_makes_one_refund(self):
        order = Order.objects.create(
            email='c@example.com',
            subtotal=Money(Decimal('20.00'), 'USD'),
            total=Money(Decimal('20.00'), 'USD'),
            payment_status='paid',
        )
        data = {'amount': '5.00', 'reason': 'customer_request', 'notes': ''}
        for _ in range(2):
            form = RefundForm(data, order=order)
            self.assertTrue(form.is_valid(), form.errors)
            form.save()
        self.assertEqual(order.refunds.count(), 1)
        self.assertEqual(order.events.filter(event_type='REFUND_CREATED').count(), 1)

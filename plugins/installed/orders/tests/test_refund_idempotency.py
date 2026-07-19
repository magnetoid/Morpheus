"""Refund idempotency key includes `notes` (deep-debug #8).

RefundService.process deduped on (order, amount, reason), so two genuinely
DISTINCT equal-value refunds (e.g. two RMAs for two equal-priced items)
collided — the second returned the first's Refund and moved no money. `notes`
(a unique `RMA <n>` per return) is now part of the key, so distinct refunds
resolve to distinct rows while a true retry (identical args) still resumes.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.orders.refunds import RefundService
from plugins.installed.orders.tests.test_refunds import _setup_order


class RefundIdempotencyTests(TestCase):
    def test_distinct_notes_do_not_collide(self):
        order, _ = _setup_order(amount='25', qty=2)  # total = 50
        r1 = RefundService.process(
            order=order,
            amount=Money(Decimal('10'), 'USD'),
            reason='customer_request',
            notes='RMA A',
        )
        r2 = RefundService.process(
            order=order,
            amount=Money(Decimal('10'), 'USD'),
            reason='customer_request',
            notes='RMA B',
        )
        # Two distinct refunds — the second used to silently reuse the first.
        self.assertNotEqual(r1.id, r2.id)
        self.assertEqual(order.refunds.count(), 2)

    def test_same_notes_resumes_same_refund(self):
        order, _ = _setup_order()
        r1 = RefundService.process(order=order, amount=Money(Decimal('5'), 'USD'), notes='RMA X')
        r2 = RefundService.process(order=order, amount=Money(Decimal('5'), 'USD'), notes='RMA X')
        # A genuine retry (identical args) still resumes the same row.
        self.assertEqual(r1.id, r2.id)
        self.assertEqual(order.refunds.count(), 1)

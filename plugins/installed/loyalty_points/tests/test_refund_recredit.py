"""Spent loyalty points must come back on a refund, not just a cancel.

Points redeemed at checkout are folded into ``Order.discount_total``, so the
cash refund already excludes them. Until v0.36 loyalty_points subscribed only
ORDER_CANCELLED, so on a refund or return the shopper simply forfeited them.
Mirrors ``gift_cards.tests.test_refund_recredit``.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.loyalty_points.models import PointsTransaction
from plugins.installed.loyalty_points.services_redeem import refund_redemption_for_order


def _usd(n):
    return Money(Decimal(str(n)), 'USD')


def _refund(amount):
    return SimpleNamespace(pk=uuid.uuid4(), amount=_usd(amount))


class LoyaltyRefundRecreditTests(TestCase):
    def setUp(self):
        self.customer = get_user_model().objects.create_user(
            username='shopper', email='s@example.com', password='x'
        )
        # 400 points spent on ORD-1; the shopper then paid $60 cash.
        PointsTransaction.objects.create(
            customer=self.customer, points=-400, reason='spend_order', order_number='ORD-1'
        )
        self.order = SimpleNamespace(order_number='ORD-1', total=_usd(60), customer=self.customer)

    def _credited(self):
        return int(
            PointsTransaction.objects.filter(
                customer=self.customer, reason='adjust', order_number='ORD-1'
            ).aggregate(t=Sum('points'))['t']
            or 0
        )

    def test_full_refund_recredits_all_points(self):
        refund_redemption_for_order(self.order, _refund(60))
        self.assertEqual(self._credited(), 400)

    def test_partial_refund_prorates(self):
        refund_redemption_for_order(self.order, _refund(30))
        self.assertEqual(self._credited(), 200)

    def test_same_refund_twice_credits_once(self):
        r = _refund(60)
        refund_redemption_for_order(self.order, r)
        refund_redemption_for_order(self.order, r)
        self.assertEqual(self._credited(), 400)

    def test_successive_partials_never_exceed_what_was_spent(self):
        for _ in range(4):  # 4 × 50% would be 800 points if uncapped
            refund_redemption_for_order(self.order, _refund(30))
        self.assertEqual(self._credited(), 400)

    def test_zero_cash_total_is_not_guessed(self):
        order = SimpleNamespace(order_number='ORD-1', total=_usd(0), customer=self.customer)
        self.assertIsNone(refund_redemption_for_order(order, _refund(0)))
        self.assertEqual(self._credited(), 0)

    def test_order_with_no_redemption_is_a_noop(self):
        order = SimpleNamespace(order_number='ORD-NOPE', total=_usd(60), customer=self.customer)
        self.assertIsNone(refund_redemption_for_order(order, _refund(60)))

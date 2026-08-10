"""Gift-card tender must come back on a refund, not just a cancel.

A card spent at checkout is folded into ``Order.discount_total``, and
``RefundService._compute_refund`` nets it back OUT of the cash refund — the
shopper is repaid only the cash they paid. Until v0.36 nothing re-credited the
card on a refund or return (gift_cards subscribed ORDER_CANCELLED only), so the
merchant silently kept it.

Proration: cash refund and card credit are shares of the same returned goods,
so both scale by ``refund.amount / order.total``.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.gift_cards import services
from plugins.installed.gift_cards.models import GiftCardLedger


def _usd(n):
    return Money(Decimal(str(n)), 'USD')


def _refund(amount):
    return SimpleNamespace(pk=uuid.uuid4(), amount=_usd(amount))


class RefundRecreditTests(TestCase):
    def setUp(self):
        # $50 card, $10 spent on ORD-1 → the shopper then paid $60 cash.
        self.card = services.issue(amount=_usd(50))
        services.redeem(code=self.card.code, amount=_usd(10), reference='ORD-1')
        self.order = SimpleNamespace(order_number='ORD-1', total=_usd(60))

    def _balance(self):
        self.card.refresh_from_db()
        return self.card.balance.amount

    def test_full_refund_recredits_whole_tender(self):
        services.refund_redemption_for_order(self.order, _refund(60))
        self.assertEqual(self._balance(), Decimal('50'))

    def test_partial_refund_prorates(self):
        # Half the order value returned → half the card tender back.
        services.refund_redemption_for_order(self.order, _refund(30))
        self.assertEqual(self._balance(), Decimal('45'))

    def test_same_refund_twice_credits_once(self):
        r = _refund(60)
        services.refund_redemption_for_order(self.order, r)
        services.refund_redemption_for_order(self.order, r)
        self.assertEqual(self._balance(), Decimal('50'))

    def test_successive_partials_never_exceed_what_was_spent(self):
        for _ in range(4):  # 4 × 50% would be 200% if uncapped
            services.refund_redemption_for_order(self.order, _refund(30))
        self.assertEqual(self._balance(), Decimal('50'))

    def test_refund_row_is_keyed_per_refund(self):
        r = _refund(60)
        services.refund_redemption_for_order(self.order, r)
        rows = GiftCardLedger.objects.filter(card=self.card, kind='refund')
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().reference, f'ORD-1:r:{r.pk}')

    def test_zero_cash_total_is_not_guessed(self):
        # Wholly tender-paid: no cash denominator to prorate against. Better to
        # log for manual handling than to invent a credit in either direction.
        order = SimpleNamespace(order_number='ORD-1', total=_usd(0))
        self.assertEqual(services.refund_redemption_for_order(order, _refund(0)), [])
        self.assertEqual(self._balance(), Decimal('40'))

    def test_order_with_no_redemption_is_a_noop(self):
        other = SimpleNamespace(order_number='ORD-NOPE', total=_usd(60))
        self.assertEqual(services.refund_redemption_for_order(other, _refund(60)), [])
        self.assertEqual(self._balance(), Decimal('40'))

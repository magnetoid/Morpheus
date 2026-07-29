"""Regression tests for gift-card redemption reversal on order cancel (Fix 3).

``services.reverse_redemption_for_order`` re-credits any gift-card balance
spent on an order — idempotent, keyed on redeem ledger rows whose
``reference == order.order_number``. It writes a ``kind='refund'`` ledger row
and skips if a refund row already exists for ``(card, reference)``. The
gift_cards plugin subscribes ``ORDER_CANCELLED`` → ``on_order_cancelled`` →
this function.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.gift_cards import services
from plugins.installed.gift_cards.models import GiftCardLedger


def _usd(n):
    return Money(Decimal(str(n)), 'USD')


class ReverseRedemptionServiceTests(TestCase):
    def _issue_and_redeem(self, reference='ORD-123'):
        """Issue a $50 card, spend $10 against ``reference`` → balance $40."""
        card = services.issue(amount=_usd(50))
        services.redeem(code=card.code, amount=_usd(10), reference=reference)
        card.refresh_from_db()
        self.assertEqual(card.balance.amount, Decimal('40'))
        return card

    def test_reversal_recredits_balance_and_writes_refund_row(self):
        card = self._issue_and_redeem('ORD-123')

        reversed_cards = services.reverse_redemption_for_order(
            SimpleNamespace(order_number='ORD-123')
        )

        self.assertEqual(len(reversed_cards), 1)
        card.refresh_from_db()
        self.assertEqual(card.balance.amount, Decimal('50'))
        refunds = GiftCardLedger.objects.filter(card=card, kind='refund', reference='ORD-123')
        self.assertEqual(refunds.count(), 1)
        self.assertEqual(refunds.first().amount_change.amount, Decimal('10'))

    def test_reversal_is_idempotent(self):
        card = self._issue_and_redeem('ORD-123')
        order = SimpleNamespace(order_number='ORD-123')

        services.reverse_redemption_for_order(order)
        second = services.reverse_redemption_for_order(order)

        # Second pass finds the existing refund row and does nothing.
        self.assertEqual(second, [])
        card.refresh_from_db()
        self.assertEqual(card.balance.amount, Decimal('50'))
        self.assertEqual(
            GiftCardLedger.objects.filter(card=card, kind='refund', reference='ORD-123').count(),
            1,
        )

    def test_no_redeem_rows_is_noop(self):
        result = services.reverse_redemption_for_order(SimpleNamespace(order_number='ORD-NONE'))
        self.assertEqual(result, [])
        self.assertEqual(GiftCardLedger.objects.filter(kind='refund').count(), 0)


class ReverseRedemptionHookTests(TestCase):
    def test_order_cancelled_hook_recredits_card(self):
        from morpheus.core import MorpheusEvents, hook_registry
        from plugins.installed.orders.models import Order

        order = Order.objects.create(
            email='buyer@example.com',
            subtotal=_usd(50),
            total=_usd(50),
        )
        card = services.issue(amount=_usd(50))
        services.redeem(code=card.code, amount=_usd(10), reference=order.order_number)
        card.refresh_from_db()
        self.assertEqual(card.balance.amount, Decimal('40'))

        hook_registry.fire(MorpheusEvents.ORDER_CANCELLED, order=order)

        card.refresh_from_db()
        self.assertEqual(card.balance.amount, Decimal('50'))
        self.assertTrue(
            GiftCardLedger.objects.filter(
                card=card, kind='refund', reference=order.order_number
            ).exists()
        )

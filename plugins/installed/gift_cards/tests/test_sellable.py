"""Sellable gift cards — a paid order containing the gift-card SKU issues
cards (one per unit) and emails the codes. Idempotent against ORDER_PAID
re-fires (webhook replays).
"""

from __future__ import annotations

from decimal import Decimal

from django.core import mail
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.gift_cards.models import GiftCard
from plugins.installed.gift_cards.services import issue_for_order
from plugins.installed.orders.models import Order, OrderItem


def _order_with(*items):
    """items = (sku, quantity, amount) tuples."""
    order = Order.objects.create(
        email='giver@example.com',
        subtotal=Money(Decimal('50'), 'USD'),
        total=Money(Decimal('50'), 'USD'),
    )
    for i, (sku, qty, amount) in enumerate(items):
        OrderItem.objects.create(
            order=order,
            product_name=f'Item {i}',
            sku=sku,
            quantity=qty,
            unit_price=Money(Decimal(amount), 'USD'),
            total_price=Money(Decimal(amount) * qty, 'USD'),
        )
    return order


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='shop@example.com',
)
class SellableGiftCardTests(TestCase):
    def test_paid_order_issues_one_card_per_unit_and_emails_codes(self):
        order = _order_with(('GIFT-CARD', 2, '25'), ('BOOK-1', 1, '10'))
        issued = issue_for_order(order)
        self.assertEqual(len(issued), 2)
        cards = GiftCard.objects.filter(issued_to_email='giver@example.com')
        self.assertEqual(cards.count(), 2)
        for card in cards:
            self.assertEqual(card.balance.amount, Decimal('25'))
            self.assertEqual(card.state, 'active')
        # one delivery email per card, each carrying its code
        self.assertEqual(len(mail.outbox), 2)
        bodies = ' '.join(m.body for m in mail.outbox)
        for card in cards:
            self.assertIn(card.code, bodies)

    def test_refire_is_idempotent(self):
        order = _order_with(('GIFT-CARD', 1, '50'))
        issue_for_order(order)
        issue_for_order(order)  # webhook replay
        self.assertEqual(GiftCard.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_non_matching_order_is_untouched(self):
        order = _order_with(('BOOK-1', 3, '10'))
        self.assertEqual(issue_for_order(order), [])
        self.assertEqual(GiftCard.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_order_paid_hook_wires_issuance(self):
        from core.hooks import MorpheusEvents, hook_registry

        order = _order_with(('GIFT-CARD', 1, '30'))
        hook_registry.fire(MorpheusEvents.ORDER_PAID, order=order)
        self.assertEqual(GiftCard.objects.count(), 1)
        self.assertEqual(GiftCard.objects.first().initial_value.amount, Decimal('30'))

"""Gift card is a TENDER, applied AFTER tax + shipping (deep-debug #7).

The gift-card application used to live in ``promotions.on_cart_breakdown`` at
hook priority 10 — but tax (priority 20) and shipping (priority 30) hadn't run
yet, so the card capped against ``subtotal − discount`` with tax/shipping still
zero. A card with enough balance to cover the whole order only paid down the
subtotal, leaving the shopper to pay tax + shipping out of pocket AND stranding
the unspent balance on the card.

The fix moves the gift-card tender to ``gift_cards.on_cart_breakdown`` at
priority 50 (its correct owner, and after every discount/tax/shipping handler),
so ``remaining = subtotal + tax + shipping − discount`` is the true order total.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.customers.models import Customer
from plugins.installed.gift_cards import services as gc_services
from plugins.installed.gift_cards.plugin import GiftCardsPlugin
from plugins.installed.orders.services import CartService, OrderService


def _usd(n):
    return Money(Decimal(str(n)), 'USD')


class GiftCardTenderCapTests(TestCase):
    """The handler math in isolation: cap against the FULL post-tax total."""

    def _cart_with_card(self, balance):
        cart = CartService.get_or_create_cart(session_key='gc-tender')
        card = gc_services.issue(amount=_usd(balance))
        cart.gift_card = card
        cart.save(update_fields=['gift_card', 'updated_at'])
        return cart, card

    def test_caps_against_subtotal_plus_tax_plus_shipping(self):
        # Value dict as it looks AFTER tax(20)+shipping(30)+discounts have run.
        cart, card = self._cart_with_card(balance=60)
        value = {
            'currency': 'USD',
            'subtotal': _usd(50),
            'shipping': _usd(10),
            'tax': _usd(5),
            'discount': _usd(0),
            'total': _usd(65),
            'meta': {},
        }
        result = GiftCardsPlugin().on_cart_breakdown(value, cart=cart)
        # $60 card, $65 order → apply the full $60, not just min($60, $50).
        self.assertEqual(result['meta']['gift_card']['amount'], '60.00')
        self.assertEqual(result['total'].amount, Decimal('5.00'))
        self.assertEqual(result['discount'].amount, Decimal('60.00'))

    def test_card_smaller_than_remaining_applies_whole_balance(self):
        cart, card = self._cart_with_card(balance=30)
        value = {
            'currency': 'USD',
            'subtotal': _usd(50),
            'shipping': _usd(10),
            'tax': _usd(5),
            'discount': _usd(0),
            'total': _usd(65),
            'meta': {},
        }
        result = GiftCardsPlugin().on_cart_breakdown(value, cart=cart)
        self.assertEqual(result['meta']['gift_card']['amount'], '30.00')
        self.assertEqual(result['total'].amount, Decimal('35.00'))


class GiftCardOrderingIntegrationTests(TestCase):
    """End-to-end through the real filter chain: the card must see tax+shipping."""

    def setUp(self):
        self.product = Product.objects.create(
            name='Book', slug='gc-order-book', sku='GCO', price=_usd(20), status='active'
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, name='HC', sku='GCO-HC', price=_usd(20)
        )
        self.customer = Customer.objects.create_user(
            email='gc@example.com', username='gcbuyer', password='x'
        )

    def test_full_chain_caps_card_against_total_with_tax_and_shipping(self):
        cart = CartService.get_or_create_cart(session_key='gc-chain', customer=self.customer)
        CartService.add_item(
            cart, str(self.product.id), quantity=2, variant_id=str(self.variant.id)
        )
        card = gc_services.issue(amount=_usd(50))  # balance $50
        cart.gift_card = card
        cart.metadata = {'shipping_rate_id': 'r1'}
        cart.save(update_fields=['gift_card', 'metadata', 'updated_at'])

        # subtotal = $40; inject tax $5 + shipping $10 via the real 20/30 handlers.
        with (
            patch(
                'plugins.installed.tax.services.compute_tax_for_cart',
                return_value={'total': _usd(5)},
            ),
            patch(
                'plugins.installed.shipping.services.quote_rate',
                return_value={'amount': _usd(10), 'name': 'Flat'},
            ),
        ):
            breakdown = OrderService.calculate_cart_breakdown(
                cart=cart, address={'country': 'US'}, shipping_rate_id='r1'
            )

        # order pre-tender = 40 + 5 + 10 = $55; $50 card applies fully (not $40).
        self.assertEqual(breakdown['tax'].amount, Decimal('5.00'))
        self.assertEqual(breakdown['shipping'].amount, Decimal('10.00'))
        self.assertEqual(breakdown['meta']['gift_card']['amount'], '50.00')
        self.assertEqual(breakdown['total'].amount, Decimal('5.00'))

"""``|priced``: a price above 0, as Money or as the GraphQL dict.

A GraphQL price is a dict, truthy whatever its amount, so a card that tested
``{% if card_price %}`` printed $0.00 for a book nothing prices (Dawnchild's home
shelf, 2026-11-21) while the same book's ORM card printed nothing.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase
from djmoney.money import Money

from plugins.installed.storefront.templatetags.pricing import priced


class PricedFilterTests(SimpleTestCase):
    def test_above_zero_is_a_price(self):
        for value in (
            Money(Decimal('0.01'), 'USD'),
            Money(Decimal('18.00'), 'EUR'),
            {'amount': '18.00', 'currency': 'USD'},
            {'amount': '0.5', 'currency': 'USD'},
        ):
            with self.subTest(value=value):
                self.assertTrue(priced(value))

    def test_zero_or_nothing_is_no_price(self):
        for value in (
            None,
            '',
            Money(0, 'USD'),
            {'amount': '0', 'currency': 'USD'},
            {'amount': '0.00', 'currency': 'USD'},
            {'currency': 'USD'},
            {'amount': 'not a number'},
            {'amount': '-1.00', 'currency': 'USD'},
        ):
            with self.subTest(value=value):
                self.assertFalse(priced(value))

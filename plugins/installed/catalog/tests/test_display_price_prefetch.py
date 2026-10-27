"""A variable product's card price reads its prefetched variants (v0.125.0).

`display_price` and `price_starts_from` filtered `self.variants` for the active ones,
which bypasses `prefetch_related('variants')`: every book card on the all-books page
cost three variant queries (127 of the page's 180 on dotbooks).
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant


def _variable(slug, prices, *, inactive=()):
    p = Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal('0'), 'USD'),
        product_type='variable',
        status='active',
    )
    for i, amount in enumerate(prices):
        ProductVariant.objects.create(
            product=p,
            name=f'V{i}',
            sku=f'{slug}-{i}',
            price=Money(Decimal(amount), 'USD'),
            is_active=i not in inactive,
        )
    return p


class PrefetchedVariantPriceTests(TestCase):
    def test_the_card_price_costs_no_query_once_variants_are_prefetched(self):
        _variable('atlas', ['12.00', '9.00'])
        product = Product.objects.prefetch_related('variants').get(slug='atlas')
        with self.assertNumQueries(0):
            self.assertEqual(product.display_price, Money(Decimal('9.00'), 'USD'))
            self.assertTrue(product.price_starts_from)

    def test_an_inactive_variant_neither_prices_nor_counts(self):
        _variable('globe', ['12.00', '5.00'], inactive=(1,))
        product = Product.objects.prefetch_related('variants').get(slug='globe')
        self.assertEqual(product.display_price, Money(Decimal('12.00'), 'USD'))
        self.assertFalse(product.price_starts_from)

    def test_without_a_prefetch_the_answers_are_the_same(self):
        _variable('map', ['7.00', '8.00'])
        product = Product.objects.get(slug='map')
        self.assertEqual(product.display_price, Money(Decimal('7.00'), 'USD'))
        self.assertTrue(product.price_starts_from)

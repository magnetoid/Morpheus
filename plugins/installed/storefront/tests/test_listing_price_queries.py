"""The product list costs the same queries for one priced card or many (v0.125.0).

A variable product's card ("From $9") re-queried its variants three times, so the
all-books page grew by three queries per book.
"""

from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant


def _variable(slug):
    p = Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal('0'), 'USD'),
        product_type='variable',
        status='active',
    )
    for i, amount in enumerate(('12.00', '9.00')):
        ProductVariant.objects.create(
            product=p, name=f'V{i}', sku=f'{slug}-{i}', price=Money(Decimal(amount), 'USD')
        )


class ListingPriceQueryTests(TestCase):
    def _queries(self) -> tuple[int, str]:
        with CaptureQueriesContext(connection) as ctx:
            html = self.client.get('/products/').content.decode()
        return len(ctx.captured_queries), html

    # The error log's capture switch is memoised for 10 s; hold it across the
    # measured pages (see test_facet_queries).
    @mock.patch('core.errors.mode._MEMO_S', 3600.0)
    def test_more_variable_products_cost_no_more_queries(self):
        from core.errors import mode

        mode.forget()
        self.addCleanup(mode.forget)
        _variable('atlas')
        self._queries()  # warm the nav, settings and capture-switch caches
        one, html = self._queries()
        self.assertIn('Atlas', html)
        for slug in ('globe', 'map', 'compass'):
            _variable(slug)
        self._queries()  # a new product clears the catalog caches: warm them again
        four, html = self._queries()
        self.assertIn('Compass', html)
        self.assertEqual(four, one)

"""The product list's facet panel costs the same queries for one filterable attribute or many.

It ran three queries per filterable attribute (two of them embedding the whole filtered
product query) — a store with ten filters paid thirty queries per listing page.
"""

from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from djmoney.money import Money

from plugins.installed.catalog.models import Attribute, AttributeValue, Product, ProductAttribute


class FacetQueryTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Lamp', slug='lamp', sku='L1', status='active', price=Money(Decimal('20'), 'USD')
        )

    def _add_filter(self, n: int) -> None:
        attr = Attribute.objects.create(name=f'Facet {n}', slug=f'facet-{n}', is_filterable=True)
        value = AttributeValue.objects.create(attribute=attr, name=f'Value {n}', slug=f'value-{n}')
        ProductAttribute.objects.create(product=self.product, attribute=attr).values.add(value)

    def _queries(self) -> tuple[int, str]:
        with CaptureQueriesContext(connection) as ctx:
            html = self.client.get('/products/').content.decode()
        return len(ctx.captured_queries), html

    # The error log's detailed-capture switch is memoised for 10 s per process; on a slow
    # runner it lapsed between the two measured pages and one paid an extra query (66 != 67).
    @mock.patch('core.errors.mode._MEMO_S', 3600.0)
    def test_more_filters_cost_no_more_queries(self):
        from core.errors import mode

        mode.forget()
        self.addCleanup(mode.forget)
        self._add_filter(1)
        self._queries()  # the first page warms the nav, settings and capture-switch caches
        one, html = self._queries()
        self.assertIn('Value 1', html)
        for n in (2, 3, 4):
            self._add_filter(n)
        four, html = self._queries()
        self.assertIn('Value 4', html)
        self.assertEqual(four, one)

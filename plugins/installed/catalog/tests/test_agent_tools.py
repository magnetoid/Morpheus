"""Catalog agent tools — products.search must report the REAL total, and
products.count answers "how many" correctly (Linda was reporting the page size).
"""

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.agent_tools import products_count_tool, products_search_tool
from plugins.installed.catalog.models import Product


def _make(n, status='active', prefix='book'):
    for i in range(n):
        Product.objects.create(
            name=f'{prefix.title()} {i}',
            slug=f'{prefix}-{i}',
            sku=f'{prefix.upper()}{i}',
            price=Money(Decimal('5.00'), 'USD'),
            product_type='simple',
            status=status,
        )


class ProductCountToolsTests(TestCase):
    def test_search_reports_total_not_page_size(self):
        _make(25)
        res = products_search_tool.invoke({'limit': 10})
        # The bug: count == len(rows) == 10. Now total is the real catalogue size.
        self.assertEqual(res.output['total'], 25)
        self.assertEqual(res.output['returned'], 10)
        self.assertEqual(len(res.output['products']), 10)

    def test_count_tool_total(self):
        _make(25)
        self.assertEqual(products_count_tool.invoke({}).output['total'], 25)

    def test_count_tool_filtered_by_status(self):
        _make(25, status='active')
        _make(3, status='draft', prefix='draft')
        self.assertEqual(products_count_tool.invoke({'status': 'active'}).output['total'], 25)
        self.assertEqual(products_count_tool.invoke({'status': 'draft'}).output['total'], 3)
        self.assertEqual(products_count_tool.invoke({}).output['total'], 28)

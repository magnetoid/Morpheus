"""Book Product model + plugin smoke tests."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.book_product.models import BookProduct, PrintType
from plugins.installed.catalog.models import Product


class BookProductModelTests(TestCase):
    def _product(self, **kw):
        defaults = {
            'name': 'A Book',
            'slug': 'a-book',
            'sku': 'BK-1',
            'price': Money(Decimal('10.00'), 'USD'),
            'product_type': 'simple',
        }
        defaults.update(kw)
        return Product.objects.create(**defaults)

    def test_one_to_one_and_defaults(self):
        product = self._product()
        book = BookProduct.objects.create(product=product, author='Ada Lovelace', page_count=288)
        self.assertEqual(product.book, book)  # related_name='book'
        self.assertEqual(book.print_type, PrintType.PAPERBACK)  # default
        self.assertEqual(book.contributors, [])

    def test_str_uses_author(self):
        product = self._product(slug='b', sku='BK-2')
        book = BookProduct.objects.create(product=product, author='Grace Hopper')
        self.assertIn('Grace Hopper', str(book))

"""Tests for the legacy book.* metafield → BookProduct backfill command."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.book_product.models import BookProduct
from plugins.installed.catalog.models import Product
from plugins.installed.metafields.models import Metafield


class BookProductBackfillCommandTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Utopia',
            slug='utopia',
            sku='BOOK-1',
            price=Money(Decimal('12.00'), 'USD'),
            product_type='simple',
        )

    def test_apply_creates_book_product_from_legacy_metafields(self):
        Metafield.objects.set(self.product, namespace='book', key='author', value='Thomas More')
        Metafield.objects.set(self.product, namespace='book', key='publisher', value='DotBooks')
        Metafield.objects.set(self.product, namespace='book', key='format', value='Hardcover')
        Metafield.objects.set(self.product, namespace='book', key='paper_type', value='Standard white')
        Metafield.objects.set(self.product, namespace='book', key='binding', value='Perfect Bound')
        Metafield.objects.set(self.product, namespace='book', key='pages', value='345')
        Metafield.objects.set(self.product, namespace='book', key='language', value='English')
        Metafield.objects.set(self.product, namespace='book', key='series_position', value='Book 2')

        out = StringIO()
        call_command('backfill_book_product', '--apply', stdout=out)

        book = BookProduct.objects.get(product=self.product)
        self.assertEqual(book.author, 'Thomas More')
        self.assertEqual(book.publisher, 'DotBooks')
        self.assertEqual(book.print_type, 'hardcover')
        self.assertEqual(book.paper_type, 'standard')
        self.assertEqual(book.binding, 'Perfect Bound')
        self.assertEqual(book.page_count, 345)
        self.assertEqual(book.language, 'en')
        self.assertEqual(book.series_position, 'Book 2')
        self.assertIn('utopia:', out.getvalue())
        self.assertIn('[APPLIED]', out.getvalue())

    def test_default_mode_is_dry_run(self):
        Metafield.objects.set(self.product, namespace='book', key='author', value='Thomas More')

        out = StringIO()
        call_command('backfill_book_product', stdout=out)

        self.assertFalse(BookProduct.objects.filter(product=self.product).exists())
        self.assertIn('[DRY-RUN]', out.getvalue())

    def test_existing_values_are_not_overwritten_without_flag(self):
        book = BookProduct.objects.create(product=self.product, author='Existing Author', language='en')
        Metafield.objects.set(self.product, namespace='book', key='author', value='Thomas More')
        Metafield.objects.set(self.product, namespace='book', key='language', value='French')
        Metafield.objects.set(self.product, namespace='book', key='publisher', value='DotBooks')

        call_command('backfill_book_product', '--apply', stdout=StringIO())

        book.refresh_from_db()
        self.assertEqual(book.author, 'Existing Author')
        self.assertEqual(book.language, 'en')
        self.assertEqual(book.publisher, 'DotBooks')

    def test_overwrite_flag_replaces_existing_values(self):
        book = BookProduct.objects.create(product=self.product, author='Existing Author')
        Metafield.objects.set(self.product, namespace='book', key='author', value='Thomas More')

        call_command('backfill_book_product', '--apply', '--overwrite', stdout=StringIO())

        book.refresh_from_db()
        self.assertEqual(book.author, 'Thomas More')

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


class BookMetafieldMigrationTests(TestCase):
    """The 0002 data migration copies book.* metafields onto the model."""

    def test_copies_book_metafields_into_model(self):
        import importlib

        from django.apps import apps as live_apps
        from django.contrib.contenttypes.models import ContentType

        mig = importlib.import_module(
            'plugins.installed.book_product.migrations.0002_migrate_book_metafields'
        )
        from plugins.installed.metafields.models import Metafield

        product = Product.objects.create(
            name='Legacy Book',
            slug='legacy',
            sku='LEG-1',
            price=Money(Decimal('9.00'), 'USD'),
            product_type='simple',
        )
        ct = ContentType.objects.get_for_model(Product)
        for key, val, vtype in (
            ('author', 'Margaret Atwood', 'string'),
            ('pages', '311', 'integer'),
            ('publisher', 'McClelland', 'string'),
        ):
            Metafield.objects.create(
                content_type=ct,
                object_id=str(product.id),
                namespace='book',
                key=key,
                value=val,
                value_type=vtype,
            )

        mig.migrate_book_metafields(live_apps, None)

        book = BookProduct.objects.get(product=product)
        self.assertEqual(book.author, 'Margaret Atwood')
        self.assertEqual(book.page_count, 311)
        self.assertEqual(book.publisher, 'McClelland')

        # Idempotent + non-clobbering: re-run doesn't overwrite an edited value.
        book.author = 'Edited Name'
        book.save()
        mig.migrate_book_metafields(live_apps, None)
        book.refresh_from_db()
        self.assertEqual(book.author, 'Edited Name')

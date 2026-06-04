"""book_product.compat — model-first, legacy-metafield-fallback reads."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.book_product import compat
from plugins.installed.book_product.models import BookProduct
from plugins.installed.catalog.models import Product
from plugins.installed.metafields.models import Metafield


class CompatTests(TestCase):
    def _product(self, slug, sku):
        return Product.objects.create(
            name=slug,
            slug=slug,
            sku=sku,
            price=Money(Decimal('5.00'), 'USD'),
            product_type='simple',
            status='active',
        )

    def setUp(self):
        # One author on the model, a different author only in legacy metafields.
        self.p_model = self._product('m', 'M-1')
        BookProduct.objects.create(product=self.p_model, author='Ada Model')
        self.p_meta = self._product('x', 'X-1')
        ct = ContentType.objects.get_for_model(Product)
        Metafield.objects.create(
            content_type=ct,
            object_id=str(self.p_meta.id),
            namespace='book',
            key='author',
            value='Bob Meta',
            value_type='string',
        )

    def test_distinct_values_unions_model_and_metafields(self):
        self.assertEqual(compat.distinct_values('author'), ['Ada Model', 'Bob Meta'])

    def test_product_ids_for_each_source(self):
        self.assertEqual(compat.product_ids_for('author', 'ada model'), [str(self.p_model.id)])
        self.assertEqual(compat.product_ids_for('author', 'Bob Meta'), [str(self.p_meta.id)])

    def test_set_book_attrs_writes_model_normalized(self):
        from plugins.installed.book_product.compat import set_book_attrs

        p = self._product('w9', 'W-9')
        set_book_attrs(
            p,
            {
                'author': 'Tolkien',
                'format': 'Paperback',
                'pages': 423,
                'published_year': 1937,
                'language': 'English',
            },
        )
        b = BookProduct.objects.get(product=p)
        self.assertEqual(b.author, 'Tolkien')
        self.assertEqual(b.print_type, 'paperback')
        self.assertEqual(b.page_count, 423)
        self.assertEqual(b.language, 'en')
        self.assertEqual(b.publication_date.year, 1937)

    def test_resolve_slug_both_sources(self):
        self.assertEqual(compat.resolve_slug('author', 'ada-model'), 'Ada Model')
        self.assertEqual(compat.resolve_slug('author', 'bob-meta'), 'Bob Meta')
        self.assertIsNone(compat.resolve_slug('author', 'nobody'))

    def test_book_attrs_model_first_and_fallback(self):
        from datetime import date

        book = BookProduct.objects.get(product=self.p_model)
        book.publisher = 'Model House'
        book.page_count = 288
        book.print_type = 'hardcover'
        book.language = 'en'
        book.publication_date = date(1999, 5, 1)
        book.save()
        attrs = compat.book_attrs(self.p_model)
        self.assertEqual(attrs['author'], 'Ada Model')
        self.assertEqual(attrs['pages'], '288')
        self.assertEqual(attrs['format'], 'hardcover')
        self.assertEqual(attrs['published_year'], '1999')
        # Metafield-only product still yields attrs via fallback.
        self.assertEqual(compat.book_attrs(self.p_meta).get('author'), 'Bob Meta')


class JsonldBookSchemaTests(TestCase):
    def test_book_schema_emitted_from_model(self):
        from plugins.installed.seo.services.jsonld import product_jsonld

        p = Product.objects.create(
            name='Hardback',
            slug='hb',
            sku='HB-1',
            price=Money(Decimal('20.00'), 'USD'),
            product_type='simple',
            status='active',
        )
        BookProduct.objects.create(
            product=p, author='Iris Model', page_count=420, print_type='hardcover'
        )
        data = product_jsonld(p)
        self.assertIn('Book', data.get('@type', []))
        self.assertEqual(data.get('numberOfPages'), 420)
        self.assertEqual((data.get('author') or {}).get('name'), 'Iris Model')
        self.assertEqual(data.get('bookFormat'), 'https://schema.org/Hardcover')

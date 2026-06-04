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

    def test_resolve_slug_both_sources(self):
        self.assertEqual(compat.resolve_slug('author', 'ada-model'), 'Ada Model')
        self.assertEqual(compat.resolve_slug('author', 'bob-meta'), 'Bob Meta')
        self.assertIsNone(compat.resolve_slug('author', 'nobody'))

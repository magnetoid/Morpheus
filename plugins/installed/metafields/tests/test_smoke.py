"""Metafield smoke test — the manager round-trips typed values."""
from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money


class MetafieldsSmoke(TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Product
        self.product = Product.objects.create(
            name='Test Book', slug='meta-test', sku='META-1',
            status='active', price=Money(Decimal('10.00'), 'USD'),
        )

    def test_set_and_for_obj(self):
        from plugins.installed.metafields.models import Metafield
        Metafield.objects.set(self.product, namespace='book', key='author',
                              value='Hanna Rieder')
        Metafield.objects.set(self.product, namespace='book', key='pages',
                              value=224)
        out = Metafield.objects.for_obj(self.product, ns='book')
        self.assertEqual(out.get('book.author'), 'Hanna Rieder')
        self.assertEqual(out.get('book.pages'), 224)

    def test_idempotent_upsert(self):
        from plugins.installed.metafields.models import Metafield
        Metafield.objects.set(self.product, namespace='book', key='author', value='A')
        Metafield.objects.set(self.product, namespace='book', key='author', value='B')
        self.assertEqual(
            Metafield.objects.filter(namespace='book', key='author').count(),
            1,
        )

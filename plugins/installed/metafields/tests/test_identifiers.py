"""Product identifier codes: metafield-backed, mapped to schema.org JSON-LD."""

from __future__ import annotations

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.metafields.identifiers import (
    identifier_values,
    product_identifiers,
)
from plugins.installed.metafields.models import Metafield
from plugins.installed.seo.services.jsonld import product_jsonld


class ProductIdentifiersTests(TestCase):
    def setUp(self):
        self.p = Product.objects.create(
            name='Codes', slug='codes', sku='CODES', price=Money(9, 'USD'), status='active'
        )

    def test_empty_when_no_codes(self):
        self.assertEqual(product_identifiers(self.p), [])
        self.assertIsNone(product_identifiers(None) or None)

    def test_reads_identifiers_namespace_with_jsonld_mapping(self):
        Metafield.objects.set(self.p, namespace='identifiers', key='ean13', value='4006381333931')
        Metafield.objects.set(self.p, namespace='identifiers', key='mpn', value='ABC-123')
        codes = {c['key']: c for c in product_identifiers(self.p)}
        self.assertEqual(codes['ean13']['value'], '4006381333931')
        self.assertEqual(codes['ean13']['jsonld'], 'gtin13')
        self.assertEqual(codes['mpn']['jsonld'], 'mpn')

    def test_isbn13_falls_back_to_legacy_book_isbn(self):
        Metafield.objects.set(self.p, namespace='book', key='isbn', value='9780000000001')
        codes = {c['key']: c for c in product_identifiers(self.p)}
        self.assertEqual(codes['isbn13']['value'], '9780000000001')
        self.assertEqual(codes['isbn13']['jsonld'], 'isbn')
        # identifier_values (editor pre-fill) does NOT apply the legacy fallback.
        self.assertEqual(identifier_values(self.p)['isbn13'], '')

    def test_jsonld_emits_codes(self):
        Metafield.objects.set(self.p, namespace='identifiers', key='ean13', value='4006381333931')
        Metafield.objects.set(self.p, namespace='book', key='isbn', value='9780000000001')
        data = product_jsonld(self.p)
        self.assertEqual(data.get('gtin13'), '4006381333931')
        self.assertEqual(data.get('isbn'), '9780000000001')

"""Shopify importer tests using offline records (no network)."""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.catalog.models import Product
from plugins.installed.importers.adapters.shopify import ShopifyImporter
from plugins.installed.importers.models import SourceMapping

_PRODUCTS = [
    {
        'id': 1001,
        'title': 'Test Blender',
        'handle': 'test-blender',
        'body_html': '<p>Powerful</p>',
        'status': 'active',
        'currency': 'USD',
        'variants': [{'id': 9001, 'sku': 'BLEND-1', 'price': '79.99', 'title': 'Default'}],
        'images': [],
    },
]


class ShopifyImporterTests(TestCase):
    def test_offline_import_creates_product_and_mapping(self):
        importer = ShopifyImporter(records={'products': _PRODUCTS})
        summary = importer.run(started_by='test')
        self.assertEqual(summary.counts.get('products'), 1)
        self.assertTrue(Product.objects.filter(slug='test-blender').exists())
        self.assertTrue(
            SourceMapping.objects.filter(
                source='shopify',
                source_id='1001',
                dest_model='Product',
            ).exists()
        )

    def test_re_import_is_idempotent(self):
        ShopifyImporter(records={'products': _PRODUCTS}).run(started_by='test')
        ShopifyImporter(records={'products': _PRODUCTS}).run(started_by='test')
        self.assertEqual(Product.objects.filter(slug='test-blender').count(), 1)
        self.assertEqual(
            SourceMapping.objects.filter(source='shopify', source_id='1001').count(),
            1,
        )

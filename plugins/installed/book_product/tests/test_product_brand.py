"""A book's brand is its publisher (v0.163.0).

book_product answers catalog's `PRODUCT_BRAND`, so the product page and every
channel feed name the publisher, ahead of the store's default brand.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.book_product.models import BookProduct
from plugins.installed.catalog.brand import product_brand
from plugins.installed.catalog.models import Product


class PublisherBrandTests(TestCase):
    def setUp(self):
        from plugins.registry import app_registry

        catalog = app_registry.get('catalog')
        catalog.set_config('default_brand', 'The Shop')
        self.addCleanup(catalog.invalidate_config_cache)
        self.book = Product.objects.create(
            name='Dune',
            slug='dune-brand',
            sku='DN-1',
            status='active',
            price=Money(Decimal('12.00'), 'USD'),
        )

    @mock.patch(
        'plugins.feed_mapping.FeedMapper._primary_image_link',
        staticmethod(lambda product: 'https://cdn.example.com/p.jpg'),
    )
    def test_the_publisher_beats_the_store_default(self):
        BookProduct.objects.create(product=self.book, publisher='Chilton Books')
        self.assertEqual(product_brand(self.book), 'Chilton Books')

        from plugins.installed.google_shopping.services import mapping, settings
        from plugins.installed.seo.services.jsonld import product_jsonld

        out = product_jsonld(self.book, base_url='https://shop.test/')
        self.assertEqual(out['brand'], {'@type': 'Brand', 'name': 'Chilton Books'})
        item = mapping.map_product(self.book, settings.feed_settings())
        self.assertEqual(item['brand'], 'Chilton Books')

    def test_a_book_with_no_publisher_takes_the_default(self):
        BookProduct.objects.create(product=self.book, publisher='')
        self.assertEqual(product_brand(self.book), 'The Shop')

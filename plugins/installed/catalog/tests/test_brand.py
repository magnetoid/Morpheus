"""A product's brand has one source (v0.163.0).

`catalog/brand.py`: an app's `PRODUCT_BRAND` answer, else the store's default
brand on catalog's settings, else none, and then the product page and every
channel feed leave the brand out. Google's merchant listing page lists `brand`
as recommended, not required
(https://developers.google.com/search/docs/appearance/structured-data/merchant-listing),
so an unknown brand costs a warning, while a made-up one ("Generic", the
seller's name) is a claim about the product that is not true.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.brand import default_brand, product_brand
from plugins.installed.catalog.models import Product

CHANNELS = (
    'google_shopping',
    'meta_commerce',
    'pinterest_commerce',
    'tiktok_commerce',
    'snapchat_commerce',
    'microsoft_commerce',
    'openai_shopping',
)


class ProductBrandTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Lamp',
            slug='lamp',
            sku='LP-1',
            status='active',
            price=Money(Decimal('9.00'), 'USD'),
        )

    def _default(self, value):
        from plugins.registry import app_registry

        catalog = app_registry.get('catalog')
        catalog.set_config('default_brand', value)
        self.addCleanup(catalog.invalidate_config_cache)

    def test_no_brand_anywhere_is_none(self):
        self.assertEqual(product_brand(self.product), '')
        self.assertEqual(product_brand(None), '')

    def test_the_store_default_is_the_fallback(self):
        self._default('  Lumen Works  ')
        self.assertEqual(default_brand(), 'Lumen Works')
        self.assertEqual(product_brand(self.product), 'Lumen Works')

    def test_a_long_brand_is_cut_to_what_the_channels_take(self):
        self._default('x' * 120)
        self.assertEqual(len(product_brand(self.product)), 70)

    def test_structured_data_states_it_only_when_known(self):
        from plugins.installed.seo.services.jsonld import product_jsonld

        out = product_jsonld(self.product, base_url='https://shop.test/')
        self.assertNotIn('brand', out)
        self._default('Lumen Works')
        out = product_jsonld(self.product, base_url='https://shop.test/')
        self.assertEqual(out['brand'], {'@type': 'Brand', 'name': 'Lumen Works'})

    @mock.patch(
        'plugins.feed_mapping.FeedMapper._primary_image_link',
        staticmethod(lambda product: 'https://cdn.example.com/p.jpg'),
    )
    def test_feeds_leave_an_unknown_brand_out(self):
        from plugins.installed.google_shopping.services import mapping, settings
        from plugins.installed.meta_commerce.services.catalog_api import _catalog_item

        item = mapping.map_product(self.product, settings.feed_settings())
        self.assertNotIn('brand', item)
        self.assertNotIn('brand', _catalog_item({**item, 'price': '9.00 USD'}))

        self._default('Lumen Works')
        item = mapping.map_product(self.product, settings.feed_settings())
        self.assertEqual(item['brand'], 'Lumen Works')
        self.assertEqual(_catalog_item({**item, 'price': '9.00 USD'})['brand'], 'Lumen Works')

    def test_the_setting_lives_on_catalog_only(self):
        from plugins.registry import app_registry

        self.assertIn(
            'default_brand', app_registry.get('catalog').get_config_schema()['properties']
        )
        for name in CHANNELS:
            plugin = app_registry.get(name)
            if plugin is None:
                continue
            with self.subTest(channel=name):
                props = (plugin.get_config_schema() or {}).get('properties', {})
                self.assertNotIn('default_brand', props)

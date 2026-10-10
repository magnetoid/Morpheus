"""The ACP feed has the shape of the 2026-04-17 feed specification.

The checkout endpoints moved to ``2026-04-17`` and the ``API-Version`` header
says so, but the feed still wrote the ``2025-09-29`` rows: ``link``,
``image_link``, ``price`` as a string next to ``currency``. The specification's
feed is a list of ``Product`` groups, each with ``variants`` carrying
``price {amount (minor units), currency}``, ``availability {available, status}``,
``media[]``, ``seller {name, links}``, ``variant_options[]`` and ``barcodes[]``.
"""

from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.test import Client, TestCase
from djmoney.money import Money

from plugins.installed.agentic_checkout.app import ACP_API_VERSION
from plugins.installed.agentic_checkout.tests.test_acp import _TOKEN, _enable_plugin_and_tokens
from plugins.installed.catalog.models import Product, ProductVariant


class FeedVariantSchemaTests(TestCase):
    def setUp(self) -> None:
        _enable_plugin_and_tokens()
        self.c = Client()
        patcher = mock.patch(
            'plugins.feed_mapping.FeedMapper._primary_image_link',
            staticmethod(lambda product: 'https://cdn.example.com/p.jpg'),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _feed(self):
        r = self.c.get('/acp/feed.json', HTTP_AUTHORIZATION=f'Bearer {_TOKEN}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['API-Version'], ACP_API_VERSION)
        return r.json()

    def test_a_simple_product_is_a_group_with_one_variant(self):
        Product.objects.create(
            name='Water filter',
            slug='water-filter',
            sku='WF-1',
            status='active',
            price=Decimal('19.99'),
            description='<p>Filters water.</p>',
        )
        data = self._feed()
        self.assertEqual(data['version'], ACP_API_VERSION)
        self.assertEqual(data['count'], 1)
        product = data['products'][0]
        self.assertEqual(product['id'], 'WF-1')
        self.assertEqual(product['title'], 'Water filter')
        self.assertTrue(product['url'].startswith('http'))
        self.assertTrue(product['url'].endswith('/products/water-filter/'))
        self.assertEqual(product['description'], {'plain': 'Filters water.'})
        self.assertEqual(
            product['media'], [{'type': 'image', 'url': 'https://cdn.example.com/p.jpg'}]
        )
        self.assertTrue(product['is_eligible_checkout'])
        for key in ('link', 'image_link', 'currency'):
            self.assertNotIn(key, product)

        self.assertEqual(len(product['variants']), 1)
        variant = product['variants'][0]
        self.assertEqual(variant['id'], 'WF-1')
        self.assertEqual(variant['title'], 'Water filter')
        self.assertEqual(variant['price'], {'amount': 1999, 'currency': 'USD'})
        self.assertEqual(variant['availability'], {'available': True, 'status': 'in_stock'})
        self.assertEqual(variant['condition'], ['new'])
        self.assertTrue(variant['seller']['name'])
        self.assertTrue(all(link['type'] and link['url'] for link in variant['seller']['links']))
        for key in ('link', 'image_link', 'currency'):
            self.assertNotIn(key, variant)

    def test_a_variable_product_lists_each_variant(self):
        product = Product.objects.create(
            name='Tee',
            slug='tee',
            sku='TEE',
            status='active',
            price=Decimal('10.00'),
            product_type='variable',
        )
        ProductVariant.objects.create(
            product=product, name='Small', sku='TEE-S', price=Money(Decimal('10.00'), 'USD')
        )
        ProductVariant.objects.create(
            product=product, name='Large', sku='TEE-L', price=Money(Decimal('12.50'), 'USD')
        )
        data = self._feed()
        self.assertEqual(data['count'], 1)
        product_row = data['products'][0]
        self.assertEqual(product_row['id'], 'TEE')
        variants = {v['id']: v for v in product_row['variants']}
        self.assertEqual(set(variants), {'TEE-S', 'TEE-L'})
        self.assertEqual(variants['TEE-L']['price'], {'amount': 1250, 'currency': 'USD'})
        self.assertEqual(
            variants['TEE-L']['variant_options'], [{'name': 'variant', 'value': 'Large'}]
        )

    def test_a_sale_price_keeps_the_list_price(self):
        Product.objects.create(
            name='Lamp',
            slug='lamp',
            sku='LAMP',
            status='active',
            price=Decimal('8.00'),
            compare_at_price=Decimal('10.00'),
        )
        variant = self._feed()['products'][0]['variants'][0]
        self.assertEqual(variant['price'], {'amount': 800, 'currency': 'USD'})
        self.assertEqual(variant['list_price'], {'amount': 1000, 'currency': 'USD'})

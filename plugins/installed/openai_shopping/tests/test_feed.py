"""The ChatGPT Shopping feed carries what OpenAI's specification requires.

Required per row: item_id, title, description, url, brand, seller_name,
image_url, availability, price; the eligibility flags; variants as rows that
share a group_id with listing_has_variations and a variant_dict; returns as
accepts_returns, return_deadline_in_days and return_policy; checkout
eligibility only with the privacy and terms URLs.
"""

from __future__ import annotations

import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.openai_shopping.feed import build_rows, coverage, render_jsonl

REQUIRED = (
    'item_id',
    'title',
    'description',
    'url',
    'brand',
    'seller_name',
    'image_url',
    'availability',
    'price',
)


class _Base(TestCase):
    def setUp(self):
        patcher = mock.patch(
            'plugins.feed_mapping.FeedMapper._primary_image_link',
            staticmethod(lambda product: 'https://cdn.example.com/p.jpg'),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _config(self, **values):
        from plugins.registry import app_registry

        plugin = app_registry.get('openai_shopping')
        originals = {k: plugin.get_config_value(k, None) for k in values}
        for k, v in values.items():
            plugin.set_config(k, v)
        self.addCleanup(lambda: [plugin.set_config(k, v) for k, v in originals.items()])


class FeedRowTests(_Base):
    def test_a_simple_product_has_every_required_field(self):
        Product.objects.create(
            name='Water filter',
            slug='water-filter',
            sku='WF-1',
            status='active',
            price=Money(Decimal('19.99'), 'USD'),
            description='<p>Filters water.</p>',
        )
        rows = build_rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        for key in REQUIRED:
            with self.subTest(key=key):
                self.assertTrue(row.get(key), key)
        self.assertEqual(row['item_id'], 'WF-1')
        self.assertEqual(row['price'], '19.99 USD')
        self.assertEqual(row['availability'], 'in_stock')
        self.assertTrue(row['url'].endswith('/products/water-filter/'))
        self.assertTrue(row['is_eligible_search'])
        self.assertFalse(row['is_eligible_checkout'])
        self.assertNotIn('seller_privacy_policy', row)
        self.assertTrue(row['accepts_returns'])
        self.assertEqual(row['return_deadline_in_days'], 30)
        self.assertTrue(row['return_policy'].endswith('/returns/'))

    def test_checkout_eligibility_brings_the_policy_urls(self):
        Product.objects.create(
            name='Lamp',
            slug='lamp',
            sku='LAMP',
            status='active',
            price=Money(Decimal('8.00'), 'USD'),
        )
        self._config(checkout_eligible=True, seller_privacy_policy='https://x.test/privacy')
        row = build_rows()[0]
        self.assertTrue(row['is_eligible_checkout'])
        self.assertEqual(row['seller_privacy_policy'], 'https://x.test/privacy')
        self.assertTrue(row['seller_tos'].endswith('/p/terms/'))

    def test_variants_share_a_group(self):
        product = Product.objects.create(
            name='Tee',
            slug='tee',
            sku='TEE',
            status='active',
            price=Money(Decimal('10.00'), 'USD'),
            product_type='variable',
        )
        for name, sku, price in (('Small', 'TEE-S', '10.00'), ('Large', 'TEE-L', '12.50')):
            ProductVariant.objects.create(
                product=product, name=name, sku=sku, price=Money(Decimal(price), 'USD')
            )
        rows = {r['item_id']: r for r in build_rows()}
        self.assertEqual(set(rows), {'TEE-S', 'TEE-L'})
        self.assertEqual(rows['TEE-L']['group_id'], 'TEE')
        self.assertTrue(rows['TEE-L']['listing_has_variations'])
        self.assertEqual(rows['TEE-L']['variant_dict'], {'variant': 'Large'})
        self.assertEqual(rows['TEE-L']['price'], '12.50 USD')

    def test_countries_come_from_the_panel_or_the_store(self):
        Product.objects.create(
            name='Lamp',
            slug='lamp',
            sku='LAMP',
            status='active',
            price=Money(Decimal('8.00'), 'USD'),
        )
        self._config(store_country='gb', target_countries='GB, IE')
        row = build_rows()[0]
        self.assertEqual(row['store_country'], 'GB')
        self.assertEqual(row['target_countries'], 'GB,IE')

    def test_jsonl_is_one_object_per_line(self):
        body = render_jsonl([{'item_id': 'a', 'title': 'Ä'}, {'item_id': 'b'}])
        lines = body.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])['title'], 'Ä')


class FeedEndpointTests(_Base):
    def test_the_feed_is_served_as_ndjson(self):
        Product.objects.create(
            name='Lamp',
            slug='lamp',
            sku='LAMP',
            status='active',
            price=Money(Decimal('8.00'), 'USD'),
        )
        r = Client().get('/feeds/openai-products.jsonl')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/x-ndjson; charset=utf-8')
        self.assertEqual(json.loads(r.content.decode().splitlines()[0])['item_id'], 'LAMP')

    def test_coverage_counts(self):
        Product.objects.create(
            name='Lamp',
            slug='lamp',
            sku='LAMP',
            status='active',
            price=Money(Decimal('8.00'), 'USD'),
        )
        rep = coverage()
        self.assertEqual((rep['active'], rep['in_feed'], rep['rows']), (1, 1, 1))
        self.assertFalse(rep['push_configured'])


class DashboardTests(TestCase):
    def test_staff_see_the_page_and_the_channel_row(self):
        c = Client()
        c.force_login(
            get_user_model().objects.create_user(
                username='oa', email='oa@x.test', password='pw', is_staff=True, is_superuser=True
            )
        )
        r = c.get('/dashboard/apps/openai_shopping/overview/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'openai-products.jsonl')
        from morpheus.core import MorpheusEvents, hook_registry

        rows = hook_registry.filter(MorpheusEvents.CHANNELS_OVERVIEW, value=[]) or []
        self.assertIn('openai_shopping', [row['name'] for row in rows])


class PushTaskTests(TestCase):
    def test_no_endpoint_means_no_push(self):
        from plugins.installed.openai_shopping.tasks import push_feed

        self.assertFalse(push_feed()['pushed'])

    def test_a_push_posts_the_feed_with_the_token(self):
        from plugins.installed.openai_shopping.tasks import push_feed
        from plugins.registry import app_registry

        plugin = app_registry.get('openai_shopping')
        plugin.set_config('push_endpoint', 'https://feeds.openai.test/ingest')
        plugin.set_config('push_token', 'tok-1')
        self.addCleanup(plugin.set_config, 'push_endpoint', '')
        self.addCleanup(plugin.set_config, 'push_token', '')
        with mock.patch('requests.post') as post:
            post.return_value = mock.Mock(status_code=202, text='')
            result = push_feed()
        self.assertTrue(result['pushed'])
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Bearer tok-1')

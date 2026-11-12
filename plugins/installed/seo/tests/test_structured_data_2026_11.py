"""What the stores claim to search and answer engines, after the Nov 2026 pass.

Each test names a gap found by reading the live dotbooks markup against Google's
documentation: an edition named only "Print", with no image or identifier of its
own; a store node with no logo or e-mail although Settings → General held them;
a return policy only Google's product pages could see; AI answer bots missing
from robots.txt; a sitemap index that said everything changed at every fetch; a
listing's ItemList that restarted at 1 on page 2; and a deleted product that
Bing kept until it next crawled the URL.
"""

from __future__ import annotations

import re
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from djmoney.money import Money

from core.models import StoreSettings
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.seo.services import product_jsonld


def _store(**fields):
    store = StoreSettings.objects.first() or StoreSettings.objects.create()
    for name, value in fields.items():
        setattr(store, name, value)
    store.save()
    return store


class EditionMarkupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            name='Edition Probe',
            slug='edition-probe',
            sku='EP-1',
            status='active',
            product_type='variable',
            price=Money(Decimal('12.00'), 'USD'),
        )
        ProductVariant.objects.create(
            product=cls.product,
            name='Print',
            sku='EP-1-P',
            variant_type='physical',
            barcode='978-0-14-044913-6',
            price=Money(Decimal('12.00'), 'USD'),
        )
        ProductVariant.objects.create(
            product=cls.product,
            name='Digital PDF',
            sku='EP-1-D',
            variant_type='digital',
            barcode='internal-7',
            price=Money(Decimal('5.00'), 'USD'),
        )

    def _members(self, **rendered):
        node = product_jsonld(
            {'slug': 'edition-probe', 'name': 'Edition Probe', **rendered}, model=self.product
        )
        return {m['sku']: m for m in node['hasVariant']}

    def test_an_edition_is_named_after_its_book(self):
        self.assertEqual(self._members()['EP-1-D']['name'], 'Edition Probe – Digital PDF')

    def test_an_edition_without_a_photo_shows_the_books(self):
        members = self._members(primary_image_url='/media/products/cover.jpg')
        self.assertTrue(members['EP-1-P']['image'].endswith('/media/products/cover.jpg'))
        self.assertEqual(members['EP-1-P']['image'], members['EP-1-D']['image'])

    def test_a_barcode_of_a_gtins_length_is_claimed_and_nothing_else(self):
        members = self._members()
        self.assertEqual(members['EP-1-P']['gtin13'], '9780140449136')
        self.assertFalse([k for k in members['EP-1-D'] if k.startswith('gtin')])

    def test_each_edition_has_its_own_id_on_the_page(self):
        member_id = self._members()['EP-1-P']['@id']
        self.assertTrue(member_id.endswith('/products/edition-probe/#variant-EP-1-P'), member_id)


class EditionPhotoQueryTests(TestCase):
    """An edition's own photo is loaded with the editions, not one query each."""

    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            name='Photo Probe',
            slug='photo-probe',
            sku='PP-1',
            status='active',
            product_type='variable',
            price=Money(Decimal('10.00'), 'USD'),
        )

    def _add_editions(self, count):
        from plugins.installed.catalog.models import ProductImage

        start = self.product.variants.count()
        for i in range(start, start + count):
            # bulk_create skips ProductImage.save(), which renders files.
            [image] = ProductImage.objects.bulk_create(
                [ProductImage(product=self.product, image=f'products/pp-{i}.jpg')]
            )
            ProductVariant.objects.create(
                product=self.product,
                name=f'Edition {i}',
                sku=f'PP-1-{i}',
                image=image,
                price=Money(Decimal('10.00'), 'USD'),
            )

    def _image_queries(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as queries:
            node = product_jsonld({'slug': 'photo-probe'}, model=self.product)
        photos = [m['image'] for m in node['hasVariant']]
        self.assertTrue(all(p.endswith('.jpg') for p in photos), photos)
        return sum('catalog_productimage' in q['sql'] for q in queries.captured_queries)

    def test_more_editions_cost_no_more_photo_queries(self):
        self._add_editions(2)
        two = self._image_queries()
        self._add_editions(3)
        self.assertEqual(self._image_queries(), two)


class StoreIdentityTests(TestCase):
    def test_a_store_that_never_opened_seo_settings_is_named_from_general(self):
        from plugins.installed.seo.services import organization_jsonld, website_jsonld

        _store(store_name='Croatia Experience', contact_email='hello@croatia.example')
        with patch(
            'plugins.installed.seo.services.jsonld._site_base_url',
            return_value='https://croatia-experience.me/',
        ):
            org = organization_jsonld()
            site = website_jsonld()
        self.assertEqual(org['name'], 'Croatia Experience')
        self.assertEqual(org['contactPoint']['email'], 'hello@croatia.example')
        self.assertEqual(site['name'], 'Croatia Experience')
        self.assertEqual(site['alternateName'], 'croatia-experience.me')

    def test_the_engines_default_name_names_no_store(self):
        from plugins.installed.seo.services import organization_jsonld

        _store(store_name='Morpheus Store')
        self.assertIsNone(organization_jsonld())

    def test_the_share_banner_is_never_the_logo(self):
        from plugins.installed.seo.services.jsonld import _store_logo

        row = SimpleNamespace(logo=None, default_social_image=SimpleNamespace(url='/media/og.jpg'))
        with patch.object(StoreSettings.objects, 'first', return_value=row):
            self.assertEqual(_store_logo(), '')
        row.logo = SimpleNamespace(url='/media/store/logo.png')
        with patch.object(StoreSettings.objects, 'first', return_value=row):
            self.assertTrue(_store_logo().endswith('/media/store/logo.png'))


class StoreReturnPolicyTests(TestCase):
    def test_the_store_node_carries_the_return_policy(self):
        from djmoney.money import Money

        from plugins.installed.catalog.models import Product
        from plugins.installed.returns_portal.seo_graph import on_seo_jsonld_graph

        _store(country='US')
        # A policy for goods sent back: the store has to sell something that ships.
        Product.objects.create(name='Mug', slug='rp-mug', status='active', price=Money(5, 'USD'))
        graph = {'@graph': [{'@type': 'OnlineStore', '@id': 'https://s.example#organization'}]}
        on_seo_jsonld_graph(graph)
        policy = graph['@graph'][0]['hasMerchantReturnPolicy']
        self.assertEqual(policy['applicableCountry'], 'US')
        self.assertEqual(policy['merchantReturnDays'], 30)


class AnswerBotTests(TestCase):
    def test_the_answer_bots_get_their_own_block(self):
        from plugins.installed.seo.services.crawler_files import render_robots_txt

        robots = render_robots_txt()
        for ua in (
            'DuckAssistBot',
            'meta-webindexer',
            'meta-externalfetcher',
            'Amzn-SearchBot',
            'Amzn-User',
            'MistralAI-User',
        ):
            self.assertIn(f'User-agent: {ua}\n', robots)

    def test_a_search_crawler_is_left_to_the_general_rules(self):
        """Applebot feeds Siri and Spotlight like Googlebot feeds Search; the
        "block AI bots by default" switch must not reach it."""
        from plugins.installed.seo.services.crawler_files import render_robots_txt

        self.assertNotIn('User-agent: Applebot\n', render_robots_txt())


class SitemapIndexLastmodTests(TestCase):
    def test_the_main_sitemap_says_when_it_last_changed(self):
        from plugins.installed.seo.services import sitemaps

        entries = [
            {'loc': 'https://s.example/a/', 'lastmod': '2026-10-01T08:00:00.123456+00:00'},
            {'loc': 'https://s.example/b/', 'lastmod': '2026-10-16T20:04:57.5+00:00'},
            {'loc': 'https://s.example/c/', 'lastmod': ''},
        ]
        with patch.object(sitemaps, '_merged_sitemap_entries', return_value=entries):
            index = sitemaps.render_sitemap_index_xml()
        blocks = re.findall(r'<sitemap>(.*?)</sitemap>', index)
        self.assertIn('<lastmod>2026-10-16T20:04:57+00:00</lastmod>', blocks[0])
        self.assertTrue(blocks[0].startswith('<loc>') and 'sitemap.xml' in blocks[0])
        # The image sitemap's newest change is not known without building it.
        self.assertNotIn('<lastmod>', blocks[1])


class ListingItemListTests(TestCase):
    def _list(self, page_obj=None, **context):
        from plugins.installed.seo.schema.graph import _list_nodes

        items = [{'name': f'Book {i}', 'url': f'https://s.example/products/b{i}/'} for i in (1, 2)]
        page = SimpleNamespace(
            context={'plp_items': items, **context},
            title='Mystery',
            description='',
            page_obj=page_obj,
        )
        [node] = _list_nodes(page, 'https://s.example/genre/mystery/')
        return node

    def test_the_count_is_the_whole_listing(self):
        self.assertEqual(self._list(seo_item_count=48)['numberOfItems'], 48)

    def test_page_two_goes_on_from_page_one(self):
        page_obj = SimpleNamespace(start_index=lambda: 25)
        positions = [i['position'] for i in self._list(page_obj)['itemListElement']]
        self.assertEqual(positions, [25, 26])

    def test_unknown_totals_count_what_is_listed(self):
        self.assertEqual(self._list()['numberOfItems'], 2)


class DeletedObjectPingTests(TestCase):
    def test_a_deleted_product_is_reported_gone(self):
        product = Product.objects.create(
            name='Gone Probe', slug='gone-probe', sku='GP-1', price=Money(1, 'USD')
        )
        with (
            patch('plugins.installed.seo.services.indexnow.ping_in_background') as ping,
            self.captureOnCommitCallbacks(execute=True),
        ):
            product.delete()
        pinged = [url for call in ping.call_args_list for url in call.args[0]]
        self.assertTrue(any(u.endswith('/products/gone-probe/') for u in pinged), pinged)

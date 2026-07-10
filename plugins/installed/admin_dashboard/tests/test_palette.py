"""The Cmd+K palette is a wide, cross-app search.

It searches every dashboard page (from the DashboardPage registry, not a
hand-list), plus live entities across orders / products / customers /
categories / collections / content, grouped into ordered sections, always
fail-soft.
"""

from __future__ import annotations

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Category, Product


def _staff():
    u = get_user_model().objects.create_user(
        username='pal', email='pal@example.com', password='x', is_staff=True
    )
    c = Client()
    c.force_login(u)
    return c


def _hits(client, q):
    resp = client.get('/dashboard/palette/search/', {'q': q})
    return json.loads(resp.content)['hits']


class PaletteSearchTests(TestCase):
    def setUp(self):
        self.client = _staff()

    def test_requires_staff(self):
        resp = Client().get('/dashboard/palette/search/', {'q': 'x'})  # anonymous
        self.assertIn(resp.status_code, (302, 403))

    def test_empty_query_returns_navigation(self):
        hits = _hits(self.client, '')
        self.assertTrue(hits)
        self.assertTrue(all(h['section'] == 'Go to' for h in hits))

    def test_nav_covers_registered_plugin_pages(self):
        # A DashboardPage (e.g. marketplace 'Vendors') is searchable — the nav
        # comes from the registry, not a hardcoded list.
        labels = [h['label'].lower() for h in _hits(self.client, 'vendor') if h['section'] == 'Go to']
        self.assertTrue(any('vendor' in x for x in labels))

    def test_product_matches_by_name_and_sku(self):
        Product.objects.create(
            name='Dune',
            slug='dune',
            sku='SKU-DUNE',
            price=Money(Decimal('9'), 'USD'),
            status='active',
        )
        by_name = [h for h in _hits(self.client, 'dune') if h['section'] == 'Products']
        by_sku = [h for h in _hits(self.client, 'SKU-DUNE') if h['section'] == 'Products']
        self.assertTrue(by_name)
        self.assertTrue(by_sku)

    def test_customer_matches_by_name(self):
        get_user_model().objects.create_user(
            username='buyer',
            email='buyer@example.com',
            password='x',
            first_name='Zelda',
            last_name='Fitz',
        )
        hits = [h for h in _hits(self.client, 'zelda') if h['section'] == 'Customers']
        self.assertTrue(hits)

    def test_category_is_searchable(self):
        Category.objects.create(name='Fiction', slug='fiction')
        hits = [h for h in _hits(self.client, 'fiction') if h['section'] == 'Categories']
        self.assertTrue(hits)
        self.assertIn('/edit/', hits[0]['url'])

    def test_storefront_escape_hatch_always_offered(self):
        hits = _hits(self.client, 'anything')
        shop = [h for h in hits if h['section'] == 'Storefront']
        self.assertEqual(len(shop), 1)
        self.assertIn('/products/?q=anything', shop[0]['url'])

    def test_every_hit_has_section_and_url(self):
        Product.objects.create(
            name='Pan', slug='pan', sku='PAN', price=Money(Decimal('5'), 'USD'), status='active'
        )
        for h in _hits(self.client, 'pan'):
            self.assertIn('section', h)
            self.assertIn('url', h)
            self.assertIn('label', h)

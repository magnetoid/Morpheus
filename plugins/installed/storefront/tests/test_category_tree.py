"""A category lists its own products and those of every active category below it.

Owner, 2026-10-12: "if we have a main Tech category with subcategories of 2 and
4 products, Tech must show at least 6, and a product can also sit in Tech
directly". The category page, the shop's category filter, the GraphQL products
query and Linda's product tools only matched a product's own category, so a
parent showed nothing unless every product was cross-listed under it by hand.
The shop's category dropdown also listed only top-level categories.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Category, Product


def _product(slug, category):
    return Product.objects.create(
        name=slug.replace('-', ' ').title(),
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal('5.00'), 'USD'),
        product_type='simple',
        status='active',
        category=category,
    )


class CategoryTreeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tech = Category.objects.create(name='Tech', slug='tech-top', sort_order=2)
        self.water = Category.objects.create(name='Water', slug='water-top', sort_order=1)
        routers = Category.objects.create(name='Routers', slug='routers-sub', parent=self.tech)
        antennas = Category.objects.create(name='Antennas', slug='antennas-sub', parent=self.tech)
        old = Category.objects.create(
            name='Old shelf', slug='old-sub', parent=self.tech, is_active=False
        )
        self.in_tech = ['router-a', 'router-b', 'antenna-a', 'antenna-b', 'antenna-c', 'antenna-d']
        for slug in self.in_tech[:2]:
            _product(slug, routers)
        for slug in self.in_tech[2:]:
            _product(slug, antennas)
        _product('tech-direct', self.tech)
        self.in_tech.append('tech-direct')
        _product('water-only', self.water)
        _product('switched-off', old)

    def _listed(self, url):
        body = self.client.get(url).content.decode()
        return {
            s for s in self.in_tech + ['water-only', 'switched-off'] if f'/products/{s}/' in body
        }

    def test_the_category_page_lists_its_subcategories_products_too(self):
        self.assertEqual(self._listed('/category/tech-top/'), set(self.in_tech))

    def test_the_shop_filter_lists_its_subcategories_products_too(self):
        self.assertEqual(self._listed('/products/?category=tech-top'), set(self.in_tech))

    def test_a_subcategory_lists_only_its_own(self):
        self.assertEqual(self._listed('/products/?category=routers-sub'), {'router-a', 'router-b'})
        body = self.client.get('/products/?category=routers-sub').content.decode()
        self.assertIn('Routers', re.search(r'<h1[^>]*>(.*?)</h1>', body, re.S).group(1))

    def test_the_dropdown_shows_each_subcategory_under_its_parent(self):
        body = self.client.get('/products/').content.decode()
        select = body.split('name="category"', 1)[1].split('</select>', 1)[0]
        mine = {'water-top', 'tech-top', 'antennas-sub', 'routers-sub', 'old-sub'}
        order = [v for v in re.findall(r'<option value="([^"]+)"', select) if v in mine]
        self.assertEqual(order, ['water-top', 'tech-top', 'antennas-sub', 'routers-sub'])

    def test_graphql_products_by_category_include_subcategories(self):
        query = '{ products(category: "tech-top", first: 50) { slug } }'
        resp = self.client.post(
            '/graphql/', data=json.dumps({'query': query}), content_type='application/json'
        )
        slugs = {p['slug'] for p in resp.json()['data']['products']}
        self.assertEqual(slugs, set(self.in_tech))

    def test_lindas_product_count_includes_subcategories(self):
        from core.agents import agent_registry

        out = agent_registry.get_tool('products.count').invoke({'category': 'tech-top'}).output
        self.assertEqual(out['total'], 7)

    def test_the_dashboard_counts_a_category_with_its_subcategories(self):
        admin = get_user_model().objects.create_user(
            username='cat-admin', email='cat@x.io', password='pw', is_staff=True, is_superuser=True
        )
        self.client.force_login(admin)
        body = self.client.get('/dashboard/categories/').content.decode()
        row = body.split('>Tech</a>', 1)[1].split('</tr>', 1)[0]
        self.assertIn('>7<', row.replace(' ', ''))

"""A category nobody described still has a meta description (v0.80.1).

The crawl after the v0.80.0 deploy found one indexable listing on dotbooks with
no meta description: `/category/books/`, whose description the merchant left
blank and which has no editorial intro. Google then writes the snippet from the
page chrome. The fallback is built from what the page lists — the category and
its first products — so it says nothing the page does not show, and the
merchant's own description always wins.
"""

from __future__ import annotations

import html
import re
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Category, Product

_DESCRIPTION = re.compile(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', re.I)


def _product(slug, category, name):
    return Product.objects.create(
        name=name,
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal('5.00'), 'USD'),
        product_type='simple',
        status='active',
        category=category,
    )


class CategoryDescriptionTests(TestCase):
    def setUp(self):
        cache.clear()

    def _description(self, path) -> str:
        head = self.client.get(path).content.decode().split('</head>', 1)[0]
        found = _DESCRIPTION.findall(head)
        self.assertEqual(len(found), 1, found)
        return html.unescape(found[0])

    def test_a_category_nobody_described_is_described_from_its_products(self):
        shelf = Category.objects.create(name='Lamp Oils', slug='lamp-oils')
        _product('amber-oil', shelf, 'Amber Oil')
        _product('cedar-oil', shelf, 'Cedar Oil')
        description = self._description('/category/lamp-oils/')
        self.assertIn('Lamp Oils', description)
        self.assertIn('Amber Oil', description)
        self.assertIn('Cedar Oil', description)

    def test_the_fallback_stays_snippet_length(self):
        shelf = Category.objects.create(name='Lamp Oils', slug='lamp-oils')
        for i in range(20):
            _product(f'long-oil-{i}', shelf, f'A Long Descriptive Lamp Oil Name Number {i}')
        description = self._description('/category/lamp-oils/')
        self.assertLessEqual(len(description), 160, description)
        self.assertIn('Lamp Oils', description)

    def test_the_merchants_description_wins(self):
        shelf = Category.objects.create(
            name='Lamp Oils', slug='lamp-oils', description='Oils for every lamp.'
        )
        _product('amber-oil', shelf, 'Amber Oil')
        self.assertEqual(self._description('/category/lamp-oils/'), 'Oils for every lamp.')

"""nav_categories context processor — feeds the storefront Genres mega menu."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase

from plugins.installed.catalog.context_processors import nav_categories
from plugins.installed.catalog.models import Category


class NavCategoriesTests(TestCase):
    def setUp(self):
        cache.clear()  # the processor caches; isolate each test

    def test_returns_roots_with_active_children_ordered(self):
        fiction = Category.objects.create(name='Fiction', slug='fiction', sort_order=0)
        Category.objects.create(name='Sci-Fi', slug='sci-fi', parent=fiction, sort_order=1)
        Category.objects.create(name='Crime', slug='crime', parent=fiction, sort_order=0)
        Category.objects.create(name='Poetry', slug='poetry', sort_order=1)

        data = nav_categories(request=None)['nav_categories']
        names = [c['name'] for c in data]
        self.assertEqual(names, ['Fiction', 'Poetry'])  # by sort_order
        fiction_children = [c['name'] for c in data[0]['children']]
        self.assertEqual(fiction_children, ['Crime', 'Sci-Fi'])  # by sort_order

    def test_inactive_categories_excluded(self):
        Category.objects.create(name='Visible', slug='visible')
        Category.objects.create(name='Hidden', slug='hidden', is_active=False)
        active = Category.objects.create(name='Active', slug='active')
        Category.objects.create(
            name='HiddenChild', slug='hidden-child', parent=active, is_active=False
        )

        data = nav_categories(request=None)['nav_categories']
        names = [c['name'] for c in data]
        self.assertIn('Visible', names)
        self.assertNotIn('Hidden', names)
        active_row = next(c for c in data if c['name'] == 'Active')
        self.assertEqual(active_row['children'], [])

    def test_empty_when_no_categories(self):
        self.assertEqual(nav_categories(request=None)['nav_categories'], [])

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


class NavAuthorsTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_distinct_sorted_authors_with_slugs(self):
        from decimal import Decimal

        from django.contrib.contenttypes.models import ContentType
        from djmoney.money import Money

        from plugins.installed.catalog.context_processors import nav_authors
        from plugins.installed.catalog.models import Product
        from plugins.installed.metafields.models import Metafield

        ct = ContentType.objects.get_for_model(Product)
        for i, name in enumerate(['Zadie Smith', 'Italo Calvino', 'Zadie Smith']):
            p = Product.objects.create(
                name=f'B{i}',
                slug=f'b{i}',
                sku=f'B-{i}',
                price=Money(Decimal('5.00'), 'USD'),
                product_type='simple',
            )
            Metafield.objects.create(
                content_type=ct,
                object_id=str(p.id),
                namespace='book',
                key='author',
                value=name,
                value_type='string',
            )
        authors = nav_authors(request=None)['nav_authors']
        names = [a['name'] for a in authors]
        self.assertEqual(names, ['Italo Calvino', 'Zadie Smith'])  # distinct + sorted
        self.assertEqual(authors[0]['slug'], 'italo-calvino')

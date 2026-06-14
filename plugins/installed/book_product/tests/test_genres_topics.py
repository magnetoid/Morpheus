"""Genre/Topic taxonomies — data migration, storefront pages, redirects, nav."""

# ruff: noqa: PLC0415
from __future__ import annotations

import importlib
from decimal import Decimal

from django.apps import apps as global_apps
from django.test import Client, TestCase
from djmoney.money import Money

from plugins.installed.book_product.models import BookProduct, Genre, Topic
from plugins.installed.catalog.models import Category, Product

_migration = importlib.import_module(
    'plugins.installed.book_product.migrations.0006_categories_to_genres'
)


def _product(slug, sku, **kw):
    return Product.objects.create(
        name=slug,
        slug=slug,
        sku=sku,
        price=Money(Decimal('9.00'), 'USD'),
        product_type='simple',
        status='active',
        **kw,
    )


class CategoriesToGenresMigrationTests(TestCase):
    def test_collapses_categories_into_genres(self):
        fiction = Category.objects.create(name='Fiction', slug='fiction')
        poetry = Category.objects.create(name='Poetry', slug='poetry')
        p = _product('novel', 'SKU1', category=fiction)
        p.additional_categories.add(poetry)
        book = BookProduct.objects.create(product=p)

        _migration.forwards(global_apps, None)

        # A single Books root now exists; the genre-categories are gone.
        self.assertTrue(Category.objects.filter(slug='books').exists())
        self.assertFalse(Category.objects.filter(slug='fiction').exists())
        self.assertFalse(Category.objects.filter(slug='poetry').exists())
        # Each old category became a Genre.
        self.assertTrue(Genre.objects.filter(slug='fiction').exists())
        self.assertTrue(Genre.objects.filter(slug='poetry').exists())
        # The product is re-homed under Books, carrying both genres.
        p.refresh_from_db()
        self.assertEqual(p.category.slug, 'books')
        self.assertEqual(set(book.genres.values_list('slug', flat=True)), {'fiction', 'poetry'})
        self.assertEqual(p.additional_categories.count(), 0)

    def test_keeps_category_referenced_by_non_book_product(self):
        comics = Category.objects.create(name='Comics', slug='comics')
        _product('mug', 'SKU2', category=comics)  # NOT a book — no BookProduct row

        _migration.forwards(global_apps, None)

        # Guard: a category still used by a non-book product is never deleted.
        self.assertTrue(Category.objects.filter(slug='comics').exists())


class GenreTopicStorefrontTests(TestCase):
    def setUp(self):
        self.c = Client()
        self.genre = Genre.objects.create(name='Fiction', slug='fiction')
        self.topic = Topic.objects.create(name='Space', slug='space')
        p = _product('dune', 'SKU3')
        self.book = BookProduct.objects.create(product=p)
        self.book.genres.add(self.genre)
        self.book.topics.add(self.topic)

    def test_genre_detail_lists_its_books(self):
        r = self.c.get('/genre/fiction/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'dune')

    def test_genre_index_renders(self):
        self.assertEqual(self.c.get('/genres/').status_code, 200)

    def test_topic_detail_lists_its_books(self):
        r = self.c.get('/topic/space/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'dune')

    def test_unknown_genre_404s(self):
        self.assertEqual(self.c.get('/genre/nope/').status_code, 404)

    def test_old_category_url_301s_to_genre(self):
        # No Category 'fiction' exists, but a Genre does → permanent redirect.
        r = self.c.get('/category/fiction/')
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r['Location'], '/genre/fiction/')

    def test_categories_index_301s_to_genres(self):
        r = self.c.get('/categories/')
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r['Location'], '/genres/')

    def test_nav_genres_context(self):
        from plugins.installed.book_product.context_processors import nav_genres

        names = [g['slug'] for g in nav_genres(None)['nav_genres']]
        self.assertIn('fiction', names)

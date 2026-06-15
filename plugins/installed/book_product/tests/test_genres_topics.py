"""Genre/Topic taxonomies — data migration, storefront pages, redirects, nav."""

# ruff: noqa: PLC0415
from __future__ import annotations

import importlib
from decimal import Decimal

from django.apps import apps as global_apps
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from djmoney.money import Money

from plugins.installed.book_product.models import BookProduct, Genre, Topic
from plugins.installed.catalog.models import Category, Product

_migration = importlib.import_module(
    'plugins.installed.book_product.migrations.0006_categories_to_genres'
)
_backfill = importlib.import_module(
    'plugins.installed.book_product.migrations.0007_backfill_remaining_books_to_genres'
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


class BackfillMigrationTests(TestCase):
    """0007 completes the collapse for products that had no BookProduct row."""

    def test_backfills_products_without_a_bookproduct_row(self):
        # Simulate the post-0006 state: Books root + a Genre, but a product still
        # on the old category with NO BookProduct row (legacy metafield book).
        # (0006 runs when the test DB is built, so 'books' already exists.)
        Category.objects.get_or_create(
            slug='books', defaults={'name': 'Books', 'lft': 1, 'rght': 2, 'level': 0, 'tree_id': 99}
        )
        Genre.objects.create(name='Thriller', slug='thriller')
        thriller = Category.objects.create(name='Thriller', slug='thriller')
        p = _product('gone-girl', 'SKU9', category=thriller)
        self.assertFalse(BookProduct.objects.filter(product=p).exists())

        _backfill.forwards(global_apps, None)

        # A BookProduct row now exists, tagged with the genre, re-homed to Books.
        book = BookProduct.objects.get(product=p)
        self.assertEqual(set(book.genres.values_list('slug', flat=True)), {'thriller'})
        p.refresh_from_db()
        self.assertEqual(p.category.slug, 'books')
        # The emptied old category is gone.
        self.assertFalse(Category.objects.filter(slug='thriller').exists())


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
        from django.core.cache import cache

        from plugins.installed.book_product.context_processors import nav_genres

        cache.clear()  # nav is cached across tests; isolate this assertion
        names = [g['slug'] for g in nav_genres(None)['nav_genres']]
        self.assertIn('fiction', names)


class GenreTopicDashboardTests(TestCase):
    """Curated management, author-style: add / edit / delete + boundaries."""

    ADD = '/dashboard/book-taxonomies/curated/genre/new/'

    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='s', email='s@x.test', password='pw', is_staff=True
        )

    def _staff_client(self):
        c = Client()
        c.force_login(self.staff)
        return c

    def test_list_shows_genre_and_topic_groups(self):
        Genre.objects.create(name='Fiction', slug='fiction')
        r = self._staff_client().get('/dashboard/book-taxonomies/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Genres')
        self.assertContains(r, 'Topics')
        self.assertContains(r, 'Fiction')

    def test_add_creates_genre(self):
        r = self._staff_client().post(self.ADD, {'name': 'Science Fiction'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Genre.objects.filter(slug='science-fiction').exists())

    def test_edit_saves_seo(self):
        g = Genre.objects.create(name='Poetry', slug='poetry')
        url = f'/dashboard/book-taxonomies/curated/genre/{g.slug}/edit/'
        r = self._staff_client().post(url, {'name': 'Poetry', 'description': 'Verse.'})
        self.assertEqual(r.status_code, 302)
        g.refresh_from_db()
        self.assertEqual(g.description, 'Verse.')

    def test_delete_removes_genre(self):
        g = Genre.objects.create(name='Essays', slug='essays')
        url = f'/dashboard/book-taxonomies/curated/genre/{g.slug}/delete/'
        self._staff_client().post(url)
        self.assertFalse(Genre.objects.filter(slug='essays').exists())

    def test_add_requires_staff(self):
        # Anonymous and non-staff are both blocked (redirect to login).
        self.assertEqual(Client().post(self.ADD, {'name': 'X'}).status_code, 302)
        self.assertFalse(Genre.objects.filter(name='X').exists())
        plain = get_user_model().objects.create_user(username='u', email='u@x.test', password='pw')
        c = Client()
        c.force_login(plain)
        self.assertEqual(c.post(self.ADD, {'name': 'Y'}).status_code, 302)
        self.assertFalse(Genre.objects.filter(name='Y').exists())

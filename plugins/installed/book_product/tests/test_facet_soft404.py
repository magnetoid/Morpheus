"""Book landing pages answer for what is ON them (v0.80.0).

A crawl of dotbooks found the taxonomy pages honest about nothing: a publisher
whose only books are withdrawn answered 200 with an empty shelf, a curated
genre with no books was indexable, all 1,527 topic pages and nine genres had no
meta description at all, `/language/English/` duplicated `/language/en/`, and
`/format/paperback/` rendered 860 books on one 1.5 MB page. The index pages
counted books of every status and described themselves as "at dot books." on
any store.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import re
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.book_product.models import BookProduct, Genre, Topic
from plugins.installed.catalog.models import Product

_ROBOTS = re.compile(r'<meta[^>]+name="robots"[^>]+content="([^"]*)"', re.I)
_DESCRIPTION = re.compile(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', re.I)


def _book(slug, *, status='active', name=None, **book_kw):
    product = Product.objects.create(
        name=name or slug.replace('-', ' ').title(),
        slug=slug,
        sku=slug.upper()[:30],
        price=Money(Decimal('10.00'), 'USD'),
        product_type='simple',
        status=status,
    )
    return BookProduct.objects.create(product=product, **book_kw)


def _head(response) -> str:
    return response.content.decode().split('</head>', 1)[0]


class ValueFacetTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_a_publisher_with_only_withdrawn_books_is_not_a_page(self):
        _book('withdrawn-title', status='archived', publisher='Ghost Press')
        self.assertEqual(self.client.get('/publisher/ghost-press/').status_code, 404)
        _book('live-title', publisher='Ghost Press')
        self.assertEqual(self.client.get('/publisher/ghost-press/').status_code, 200)

    def test_a_language_written_out_redirects_to_its_code(self):
        _book('english-written', language='English')
        _book('english-coded', language='en')
        response = self.client.get('/language/English/')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/language/en/')
        body = self.client.get('/language/en/').content.decode()
        self.assertIn('english-written', body)
        self.assertIn('english-coded', body)

    def test_a_big_shelf_is_paginated_and_a_missing_page_is_a_404(self):
        for n in range(50):
            _book(f'paper-{n:02d}', print_type='paperback')
        first = self.client.get('/format/paperback/')
        self.assertEqual(first.status_code, 200)
        self.assertIn('?page=2', first.content.decode())
        self.assertEqual(self.client.get('/format/paperback/?page=2').status_code, 200)
        self.assertEqual(self.client.get('/format/paperback/?page=3').status_code, 404)

    def test_every_landing_describes_itself(self):
        _book('described-1', name='First Light', publisher='Lantern Books')
        _book('described-2', name='Second Wind', publisher='Lantern Books')
        description = _DESCRIPTION.search(_head(self.client.get('/publisher/lantern-books/')))
        self.assertIsNotNone(description)
        self.assertIn('First Light', description.group(1) + ' ')
        self.assertIn('Lantern Books', description.group(1))


class CuratedTermTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_an_empty_genre_renders_but_stays_out_of_the_index(self):
        Genre.objects.create(name='Empty Genre', slug='empty-genre', is_active=True)
        response = self.client.get('/genre/empty-genre/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(_ROBOTS.findall(_head(response)), ['noindex, follow'])

    def test_a_topic_without_copy_gets_a_description_from_its_shelf(self):
        topic = Topic.objects.create(name='Honey Production', slug='honey-production')
        book = _book('hive-notes', name='Hive Notes')
        book.topics.add(topic)
        description = _DESCRIPTION.search(_head(self.client.get('/topic/honey-production/')))
        self.assertIsNotNone(description, 'a topic page shipped without a meta description')
        self.assertIn('Honey Production', description.group(1))
        self.assertIn('Hive Notes', description.group(1))

    def test_a_genre_description_falls_back_to_its_editorial_copy(self):
        genre = Genre.objects.create(
            name='Slow Fiction',
            slug='slow-fiction',
            description='<p>Novels that take their time.</p>',
        )
        _book('slow-one').genres.add(genre)
        description = _DESCRIPTION.search(_head(self.client.get('/genre/slow-fiction/')))
        self.assertEqual(description.group(1), 'Novels that take their time.')


class TaxonomyRootTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_the_index_lists_only_publishers_with_books_in_print(self):
        _book('in-print', publisher='Live House')
        _book('out-of-print', status='archived', publisher='Gone House')
        body = self.client.get('/publishers/').content.decode()
        self.assertIn('/publisher/live-house/', body)
        self.assertNotIn('/publisher/gone-house/', body)

    def test_the_index_does_not_name_another_store(self):
        _book('any-title', publisher='Any House')
        description = _DESCRIPTION.search(_head(self.client.get('/publishers/'))).group(1)
        self.assertNotIn('dot books', description.lower())

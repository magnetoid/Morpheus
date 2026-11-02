"""Genres and authors in the storefront's search dropdown (`search_suggestions.py`)."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.book_product.models import BookProduct, Genre
from plugins.installed.catalog.models import Product


def _book(slug, *, author='', genres=(), status='active'):
    product = Product.objects.create(
        name=slug,
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal('9.00'), 'USD'),
        product_type='simple',
        status=status,
    )
    book = BookProduct.objects.create(product=product, author=author)
    book.genres.set(genres)
    return book


class BookSuggestionTests(TestCase):
    def _groups(self, q):
        return {
            g['key']: g['items']
            for g in self.client.get('/api/quick-search/', {'q': q}).json()['groups']
        }

    def test_genres_with_active_books_are_suggested(self):
        fantasy = Genre.objects.create(name='Fantasy')
        Genre.objects.create(name='Fantastic Voyages')  # no books
        withdrawn = Genre.objects.create(name='Fantasy Classics')
        _book('a-princess-of-mars', genres=[fantasy])
        _book('withdrawn', genres=[withdrawn], status='draft')
        self.assertEqual(
            self._groups('fant')['genres'],
            [{'name': 'Fantasy', 'url': f'/genre/{fantasy.slug}/', 'meta': '1 book'}],
        )

    def test_authors_are_suggested_by_any_word_of_their_name(self):
        _book('nineteen-eighty-four', author='George Orwell')
        _book('animal-farm', author='George Orwell')
        _book('withdrawn', author='George Orwellian', status='draft')
        self.assertEqual(
            self._groups('orwell')['authors'],
            [{'name': 'George Orwell', 'url': '/author/george-orwell/', 'meta': '2 books'}],
        )
        # The author page the link opens is the one the storefront serves.
        self.assertEqual(self.client.get('/author/george-orwell/').status_code, 200)

    def test_nothing_is_added_when_nothing_matches(self):
        _book('dracula', author='Bram Stoker')
        self.assertEqual(self._groups('dune'), {})

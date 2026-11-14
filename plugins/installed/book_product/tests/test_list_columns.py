"""book_product's Author and Genres columns on the dashboard product list.

A book is filed by genre, not by catalog category, so the list's Category column is
empty for every book. The columns appear only on a page that lists a book, read the
whole page in two queries, and leave with the app when it is switched off.
"""

from __future__ import annotations

import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.book_product.list_columns import annotate
from plugins.installed.book_product.models import BookProduct, Genre
from plugins.installed.catalog.models import Product
from plugins.registry import app_registry

URL = '/dashboard/products/'


def _product(slug: str) -> Product:
    return Product.objects.create(
        name=f'Item {slug}',
        slug=slug,
        sku=f'SKU-{slug}',
        status='active',
        price=Money(Decimal('9.00'), 'USD'),
    )


class BookListColumnTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username='booklister', email='booklister@example.com', password='x', is_staff=True
        )
        self.client.force_login(user)

    def _book(self, slug: str, author: str, *genres: Genre) -> Product:
        product = _product(slug)
        book = BookProduct.objects.create(product=product, author=author)
        book.genres.add(*genres)
        return product

    def _body(self) -> str:
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_a_book_shows_its_author_and_active_genres(self):
        shown = Genre.objects.create(name='Qzgothic', slug='qzgothic')
        retired = Genre.objects.create(name='Qzretired', slug='qzretired', is_active=False)
        self._book('dracula', 'Qzstoker', shown, retired)
        _product('mug')

        body = self._body()

        self.assertIn('data-col="author"', body)
        self.assertIn('data-col="genres"', body)
        row = next(r for r in re.findall(r'<tr\b.*?</tr>', body, flags=re.S) if 'SKU-dracula<' in r)
        self.assertIn('Qzstoker', row)
        self.assertIn('Qzgothic', row)
        self.assertNotIn('Qzretired', row)
        # The Columns menu offers them too.
        self.assertIn('type="checkbox" value="author"', body)

    def test_a_page_with_no_book_has_no_book_columns(self):
        _product('mug')

        body = self._body()

        self.assertNotIn('data-col="author"', body)
        self.assertNotIn('data-col="genres"', body)

    def test_switched_off_the_columns_leave(self):
        self._book('offbook', 'Qzoffauthor')
        if 'book_product' in app_registry._active:
            app_registry._active.discard('book_product')
            self.addCleanup(app_registry._active.add, 'book_product')

        body = self._body()

        self.assertNotIn('data-col="author"', body)
        self.assertNotIn('Qzoffauthor', body)

    def test_annotate_reads_the_page_in_two_queries(self):
        genre = Genre.objects.create(name='Qzcount', slug='qzcount')
        products = [self._book(f'count{i}', f'Author {i}', genre) for i in range(5)]
        products.append(_product('plain'))

        with self.assertNumQueries(2):
            self.assertTrue(annotate(products))

        self.assertEqual(products[0].book_author, 'Author 0')
        self.assertEqual(products[0].book_genres, ['Qzcount'])
        self.assertEqual((products[-1].book_author, products[-1].book_genres), ('', []))

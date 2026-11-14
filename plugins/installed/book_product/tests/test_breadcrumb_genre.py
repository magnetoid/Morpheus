"""A book's product page sits under its genre page (PRODUCT_BREADCRUMB_CATEGORY, v0.161.0).

The genre is the one a book card names: the first active genre in the genres' own
order. A book without one, and anything that is not a book, keeps the storefront's
category crumbs.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.book_product.models import BookProduct, Genre
from plugins.installed.catalog.models import Category, Product
from plugins.installed.storefront.breadcrumbs import product_category_crumbs


class GenreCrumbTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name='Shelf', slug='shelf')
        cls.product = Product.objects.create(
            name='Crumb Book',
            slug='crumb-book',
            sku='CRUMB-BOOK',
            price=Money(Decimal('9'), 'USD'),
            product_type='simple',
            status='active',
            category=cls.category,
        )

    def setUp(self):
        self.request = RequestFactory().get('/products/crumb-book/')

    def _crumbs(self, product):
        return product_category_crumbs(self.request, product=product, category=self.category)

    def test_a_product_that_is_no_book_keeps_its_category(self):
        self.assertEqual(
            self._crumbs(self.product),
            [{'name': 'Shelf', 'url': 'http://testserver/category/shelf/'}],
        )

    def test_the_first_active_genre_in_order_is_the_parent(self):
        book = BookProduct.objects.create(product=self.product)
        off = Genre.objects.create(name='Off', slug='off', is_active=False, sort_order=0)
        later = Genre.objects.create(name='Later', slug='later', sort_order=5)
        first = Genre.objects.create(name='First', slug='first', sort_order=1)
        book.genres.add(off, later, first)
        expected = [{'name': 'First', 'url': 'http://testserver/genre/first/'}]
        self.assertEqual(self._crumbs(self.product), expected)
        # The product page may hand over its GraphQL dict instead of the row.
        self.assertEqual(self._crumbs({'slug': 'crumb-book'}), expected)

    def test_a_book_without_an_active_genre_keeps_its_category(self):
        book = BookProduct.objects.create(product=self.product)
        book.genres.add(Genre.objects.create(name='Off', slug='off', is_active=False))
        self.assertEqual(self._crumbs(self.product)[0]['name'], 'Shelf')

"""The all-books page asks the book app for its filters (LISTING_FACETS).

The storefront used to filter `book__genres__slug` and import book_product for
authors itself; now it fires one filter and renders what comes back, so a store
without the book app simply has no book filters.
"""

from __future__ import annotations

from decimal import Decimal
from urllib.parse import parse_qs

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.book_product.models import BookProduct, Genre
from plugins.installed.catalog.models import Product
from plugins.registry import app_registry


def _book(slug, author, genres=()):
    p = Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal('9.00'), 'USD'),
        product_type='simple',
        status='active',
    )
    b = BookProduct.objects.create(product=p, author=author, page_count=200)
    b.genres.set(genres)
    return p


class SeamTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mystery = Genre.objects.create(name='Mystery', slug='mystery')
        cls.poetry = Genre.objects.create(name='Poetry', slug='poetry')
        _book('murder', 'Agatha Christie', [cls.mystery])
        _book('verses', 'Emily Dickinson', [cls.poetry])
        _book('tea', 'Agatha Christie', [cls.poetry])

    def _ctx(self, query=''):
        resp = self.client.get(f'/products/{query}')
        self.assertEqual(resp.status_code, 200)
        return resp.context

    def _slugs(self, ctx):
        return {p.slug for p in ctx['products']}

    def test_the_view_uses_the_queryset_the_book_app_returns(self):
        ctx = self._ctx('?genre=mystery&genre=poetry&author=Agatha%20Christie')
        self.assertEqual(self._slugs(ctx), {'murder', 'tea'})
        self.assertTrue(ctx['listing_facets'])
        self.assertEqual(ctx['result_count'], 2)
        self.assertEqual(ctx['chosen_count'], 3)

    def test_old_single_value_links_keep_their_heading(self):
        ctx = self._ctx('?author=Agatha%20Christie')
        self.assertEqual(self._slugs(ctx), {'murder', 'tea'})
        self.assertEqual(ctx['selected_author'], 'Agatha Christie')
        self.assertEqual(ctx['plp_name'], 'Books by Agatha Christie')
        ctx = self._ctx('?genre=mystery')
        self.assertEqual(ctx['selected_genre_label'], 'Mystery')

    def test_a_chip_removes_exactly_its_value_and_keeps_the_rest(self):
        ctx = self._ctx('?genre=mystery&genre=poetry&sort=name')
        chip = next(c for c in ctx['filter_chips'] if c['label'] == 'Genre: Mystery')
        self.assertEqual(
            parse_qs(chip['href'].lstrip('?')), {'genre': ['poetry'], 'sort': ['name']}
        )

    def test_pagination_keeps_repeated_keys(self):
        ctx = self._ctx('?genre=mystery&genre=poetry')
        self.assertEqual(parse_qs(ctx['paginator_base_qs']), {'genre': ['mystery', 'poetry']})

    def test_book_sorts_are_offered(self):
        keys = [k for k, _l in self._ctx()['listing_sorts']]
        self.assertEqual(
            keys, ['newest', 'name', 'author', 'price_asc', 'price_desc', 'shortest', 'longest']
        )

    def test_without_the_book_app_the_parameters_are_ignored_and_no_facets_render(self):
        self.addCleanup(app_registry.activate, 'book_product')
        app_registry.deactivate('book_product')
        ctx = self._ctx('?genre=mystery&author=Nobody&format=print&length=500-plus')
        self.assertEqual(self._slugs(ctx), {'murder', 'verses', 'tea'})
        self.assertEqual(ctx['listing_facets'], [])
        self.assertEqual(
            [k for k, _l in ctx['listing_sorts']], ['newest', 'name', 'price_asc', 'price_desc']
        )

    def test_removing_the_search_chip_keeps_the_book_filters(self):
        ctx = self._ctx('?q=murder&genre=mystery')
        chip = next(c for c in ctx['filter_chips'] if c['label'] == 'Search: murder')
        self.assertEqual(parse_qs(chip['href'].lstrip('?')), {'genre': ['mystery']})

    def test_a_chip_is_removable_when_the_url_differs_from_the_clean_value(self):
        # A lower-case author link, and a phone search with a trailing space.
        ctx = self._ctx('?author=agatha%20christie')
        chip = next(c for c in ctx['filter_chips'] if c['label'].startswith('Author:'))
        self.assertEqual(chip['href'], '/products/')
        ctx = self._ctx('?q=murder%20&genre=mystery')
        chip = next(c for c in ctx['filter_chips'] if c['label'].startswith('Search:'))
        self.assertEqual(parse_qs(chip['href'].lstrip('?')), {'genre': ['mystery']})

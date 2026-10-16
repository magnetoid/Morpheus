"""dot_books' all-books toolbar renders the book filters as panels of checkboxes.

Each filter is a <details> panel inside the one GET form, so without JavaScript
ticking boxes and pressing Apply submits repeated keys; listing-filters.js adds
apply-on-close, in-panel search and the phone sheet.
"""

from __future__ import annotations

from decimal import Decimal

from django.template.loader import get_template
from django.test import TestCase
from djmoney.money import Money

from themes.test_head_contract import _activate_theme


class DotBooksListingFiltersTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.book_product.models import BookProduct, Genre, Topic
        from plugins.installed.catalog.models import Product

        cls.mystery = Genre.objects.create(name='Mystery', slug='mystery')
        love = Topic.objects.create(name='Love', slug='love')
        for i, author in enumerate(['Agatha Christie', 'Agatha Christie', 'Emily Brontë']):
            p = Product.objects.create(
                name=f'Book {i}',
                slug=f'book-{i}',
                sku=f'BK-{i}',
                price=Money(Decimal('9.00'), 'USD'),
                product_type='simple',
                status='active',
            )
            b = BookProduct.objects.create(product=p, author=author, page_count=200 + i)
            b.genres.set([cls.mystery])
            b.topics.set([love])

    def setUp(self):
        _activate_theme(self, 'dot_books')

    def _page(self, query=''):
        resp = self.client.get(f'/products/{query}')
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def test_the_partial_compiles(self):
        get_template('storefront/_listing_filters.html')

    def test_every_facet_is_a_panel_of_named_checkboxes_with_counts(self):
        html = self._page()
        for key in ('genre', 'topic', 'author', 'format', 'length'):
            self.assertIn(f'data-facet="{key}"', html)
        self.assertIn('name="genre" value="mystery"', html)
        self.assertIn('<span class="plp-option-count">3</span>', html)
        self.assertIn('data-panel-search', html)  # topic and author
        self.assertIn('dot_books/listing-filters.js', html)

    def test_chosen_values_are_checked_and_shown_as_removable_chips(self):
        html = self._page('?author=Agatha%20Christie&genre=mystery')
        self.assertIn('name="author" value="Agatha Christie" checked', html)
        self.assertIn('Author: Agatha Christie', html)
        self.assertIn('Clear all', html)

    def test_the_sort_menu_has_the_book_orders(self):
        html = self._page()
        for label in (
            'Newest',
            'Title A–Z',
            'Author A–Z',
            'Price ↑',
            'Price ↓',
            'Shortest',
            'Longest',
        ):
            self.assertIn(label, html)

    def test_the_intro_no_longer_promises_a_publisher_filter(self):
        html = self._page()
        self.assertIn('Filter by genre, topic, author, format or length.', html)
        self.assertNotIn('Filter by genre or publisher', html)

    def test_the_old_author_box_is_gone(self):
        self.assertNotIn('plp-author-list', self._page())

    def test_the_page_has_no_search_box_of_its_own(self):
        # Owner, 2026-10-16: one search, in the header. A query arriving from the
        # header's quick search rides along while filtering and shows as a chip.
        html = self._page()
        self.assertNotIn('class="plp-search"', html)
        html = self._page('?q=agatha')
        self.assertIn('<input type="hidden" name="q" value="agatha">', html)
        self.assertIn('Search: agatha', html)

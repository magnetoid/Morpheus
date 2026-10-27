"""dot_books' book card names the genre, the author and the formats (owner, 2026-10-16).

The card showed neither genre nor author: it read `product.author`, which a
catalog Product does not have (the author is on its BookProduct), so no card on
the all-books page ever named its author. The book app now supplies a card's
genre, author and formats through one tag; on the all-books page those come
prefetched with the listing, so a grid costs no query per card.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from djmoney.money import Money

from themes.test_head_contract import _activate_theme


def _book(slug, *, author, genres, variants=(), name=None):
    from plugins.installed.book_product.models import BookProduct
    from plugins.installed.catalog.models import Product, ProductVariant

    p = Product.objects.create(
        name=name or slug.replace('-', ' ').title(),
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal('9.00'), 'USD'),
        product_type='variable' if variants else 'simple',
        status='active',
    )
    b = BookProduct.objects.create(product=p, author=author, page_count=200)
    b.genres.set(genres)
    for i, (vname, vtype) in enumerate(variants):
        ProductVariant.objects.create(
            product=p,
            name=vname,
            sku=f'{slug}-{i}',
            price=Money(Decimal('9.00'), 'USD'),
            variant_type=vtype,
        )
    return p


class BookCardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.book_product.models import Genre

        cls.mystery = Genre.objects.create(name='Mystery', slug='mystery')
        cls.poetry = Genre.objects.create(name='Poetry', slug='poetry')
        cls.murder = _book(
            'murder-at-dawn',
            author='Agatha Christie',
            genres=[cls.mystery],
            variants=[('Print', 'physical'), ('Digital PDF', 'digital')],
            name='The Murder at Dawn',
        )
        cls.poems = _book('collected-poems', author='Emily Dickinson', genres=[cls.poetry])

    def setUp(self):
        _activate_theme(self, 'dot_books')

    def _page(self, query=''):
        resp = self.client.get(f'/products/{query}')
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def _card(self, html, slug):
        start = html.index(f'href="/products/{slug}/"')
        end = html.find('data-product-card', start)  # this card only, never the next
        return html[start : end if end != -1 else start + 4000]

    def test_a_card_names_its_genre_author_and_formats(self):
        card = self._card(self._page(), 'murder-at-dawn')
        self.assertIn('<p class="book__genre">Mystery</p>', card)
        self.assertIn('Agatha Christie', card)
        self.assertIn('<p class="book__formats">Print · PDF</p>', card)

    def test_a_print_only_book_has_no_formats_line(self):
        card = self._card(self._page(), 'collected-poems')
        self.assertIn('Emily Dickinson', card)
        self.assertNotIn('book__formats', card)

    def test_a_cover_is_offered_at_the_width_the_grid_shows(self):
        # A desktop grid shows a cover about 224px wide; the smallest choice was 400px,
        # so Lighthouse counted most of every cover's bytes as wasted (v0.125.0).
        from plugins.installed.catalog.models import ProductImage

        ProductImage.objects.create(product=self.murder, image='products/murder.png')
        html = self._page()
        start = html.index('href="/products/murder-at-dawn/" class="book__hit"')
        card = html[start : start + 3000]
        self.assertIn('/img/avif/240/products/murder.png 240w', card)
        self.assertIn('sizes="(min-width: 1600px) calc((100vw - 270px) / 5)', card)

    def test_a_cover_in_a_rail_is_offered_at_the_rails_width(self):
        # A rail card is 232px from 1024px up; the grid's sizes would claim 458px on a
        # 2560px screen and fetch a 600px cover.
        from django.template.loader import render_to_string

        from plugins.installed.catalog.models import ProductImage

        ProductImage.objects.create(product=self.murder, image='products/murder.png')
        card = render_to_string(
            'storefront/_product_card.html', {'product': self.murder, 'in_rail': True}
        )
        self.assertIn('sizes="(min-width: 1024px) 232px, (min-width: 640px) 220px', card)

    def test_a_book_without_a_cover_gets_a_typeset_placeholder(self):
        card = self._card(self._page(), 'murder-at-dawn')
        self.assertIn('<span class="placeholder__title">The Murder at Dawn</span>', card)
        self.assertIn('<span class="placeholder__author">Agatha Christie</span>', card)

    def test_the_grid_costs_no_book_query_per_card(self):
        def book_queries():
            with CaptureQueriesContext(connection) as ctx:
                self._page()
            return sum(1 for q in ctx.captured_queries if 'book_product_' in q['sql'])

        two = book_queries()
        for i in range(4):
            _book(
                f'extra-{i}',
                author=f'Author {i}',
                genres=[self.poetry],
                variants=[('Print', 'physical'), ('Audiobook', 'audiobook')],
            )
        self.assertEqual(book_queries(), two)

    def test_the_tag_also_reads_a_graphql_shaped_product(self):
        from django.template import Context, Template

        out = Template(
            '{% load morph %}{% product_card_meta p as bc %}{{ bc.genre }}|{{ bc.author }}|{{ bc.formats|join:"," }}'
        ).render(Context({'p': {'id': str(self.murder.pk), 'slug': self.murder.slug}}))
        self.assertEqual(out, 'Mystery|Agatha Christie|Print,PDF')

    def test_with_the_book_app_off_the_card_shows_no_book_data(self):
        from plugins.registry import app_registry

        self.addCleanup(app_registry.activate, 'book_product')
        app_registry.deactivate('book_product')
        html = self._page()
        self.assertNotIn('<p class="book__genre">', html)  # the CSS names the class too

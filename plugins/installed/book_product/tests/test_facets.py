"""Book facet landing pages + dashboard 'Appears on' chips."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.book_product.models import BookProduct
from plugins.installed.catalog.models import Product


def _book(slug, sku, **book_kw):
    p = Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=sku,
        price=Money(Decimal('10.00'), 'USD'),
        product_type='simple',
        status='active',
    )
    return BookProduct.objects.create(product=p, **book_kw)


class BookFacetPageTests(TestCase):
    def test_publisher_page_lists_its_books(self):
        _book('a', 'A-1', publisher='Pelican Press')
        _book('b', 'B-1', publisher='Pelican Press')
        _book('c', 'C-1', publisher='Other House')
        r = self.client.get('/publisher/pelican-press/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Pelican Press')
        self.assertContains(r, 'A')  # one of its books
        self.assertNotContains(r, 'Other House')

    def test_format_and_language_pages(self):
        _book('h', 'H-1', print_type='hardcover', language='en')
        self.assertEqual(self.client.get('/format/hardcover/').status_code, 200)
        self.assertEqual(self.client.get('/language/en/').status_code, 200)

    def test_series_orders_by_position(self):
        _book('s2', 'S-2', series='Discworld', series_position='2')
        _book('s1', 'S-1', series='Discworld', series_position='1')
        r = self.client.get('/series/discworld/')
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertLess(body.index('S1'), body.index('S2'))  # position 1 before 2

    def test_unknown_facet_404(self):
        self.assertEqual(self.client.get('/publisher/nobody/').status_code, 404)
        self.assertEqual(self.client.get('/format/hardcover/').status_code, 404)  # no books

    def test_pdp_specs_link_to_facets(self):
        from plugins.installed.storefront.views.catalog import _book_specs

        _book(
            'linked',
            'L-1',
            author='Borges',
            publisher='Sur',
            print_type='hardcover',
            language='en',
            imprint='Vintage',
            series='Ficciones',
        )
        links = {s['label']: s['link'] for s in _book_specs('linked')}
        self.assertEqual(links['Author'], '/author/borges/')
        self.assertEqual(links['Publisher'], '/publisher/sur/')
        self.assertEqual(links['Imprint'], '/imprint/vintage/')
        self.assertEqual(links['Format'], '/format/hardcover/')
        self.assertEqual(links['Language'], '/language/en/')
        self.assertEqual(links['Series'], '/series/ficciones/')

    def test_dashboard_widget_facet_links(self):
        from plugins.installed.book_product.dashboard import book_widget_context

        book = _book('z', 'Z-1', author='Borges', publisher='Sur', print_type='paperback')
        facets = book_widget_context(book.product)['facets']
        urls = {f['url'] for f in facets}
        self.assertIn('/author/borges/', urls)
        self.assertIn('/publisher/sur/', urls)
        self.assertIn('/format/paperback/', urls)

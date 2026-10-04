"""Facet links are built only for values the facet routes can serve.

The PDP spec rows and the dashboard's facet list linked ``/format/<print_type>/``
from the raw stored value. The route is ``format/<slug:value>/``, so a free-text
value such as ``PDF report`` produced a link that 404s.
"""

from __future__ import annotations

from decimal import Decimal
from urllib.parse import urlencode

from django.test import TestCase
from django.utils.text import slugify
from djmoney.money import Money


def _book(slug: str, print_type: str):
    from plugins.installed.book_product.models import BookProduct
    from plugins.installed.catalog.models import Product

    product = Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=f'SKU-{slug}',
        price=Money(Decimal('9.00'), 'USD'),
        product_type='simple',
        status='active',
    )
    return BookProduct.objects.create(product=product, print_type=print_type)


class FacetLinkTests(TestCase):
    def test_dashboard_facets_skip_an_unroutable_format(self):
        from plugins.installed.book_product.dashboard import _facets

        urls = [f['url'] for f in _facets(_book('a-report', 'PDF report'), slugify)]
        self.assertNotIn('/format/PDF report/', urls)
        self.assertFalse(any(' ' in u for u in urls), urls)

    def test_dashboard_facets_link_a_routable_format(self):
        from plugins.installed.book_product.dashboard import _facets

        urls = [f['url'] for f in _facets(_book('a-paperback', 'paperback'), slugify)]
        self.assertIn('/format/paperback/', urls)

    def test_pdp_spec_row_has_no_link_for_an_unroutable_format(self):
        from plugins.installed.storefront.views.catalog import _book_specs_from_model

        _book('a-report', 'PDF report')
        row = next(
            r
            for r in _book_specs_from_model('a-report', slugify, urlencode)
            if r['label'] == 'Format'
        )
        self.assertEqual(row['value'], 'PDF report')
        self.assertEqual(row['link'], '')

    def test_pdp_spec_row_links_a_routable_format(self):
        from plugins.installed.storefront.views.catalog import _book_specs_from_model

        _book('a-paperback', 'paperback')
        row = next(
            r
            for r in _book_specs_from_model('a-paperback', slugify, urlencode)
            if r['label'] == 'Format'
        )
        self.assertEqual(row['link'], '/format/paperback/')

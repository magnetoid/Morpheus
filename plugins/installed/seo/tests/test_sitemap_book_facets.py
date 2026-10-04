"""A book facet is listed in the sitemap only when its URL can be served.

``print_type`` is an enum-ish CharField but accepts free text; one live book
stored ``PDF report``. The sitemap emitted ``/format/PDF report/`` while the
route is ``format/<slug:value>/``, so the sitemap pointed crawlers at a 404.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
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


class SitemapBookFacetTests(TestCase):
    def test_a_routable_print_type_is_listed(self):
        from plugins.installed.seo.services import render_sitemap_xml

        _book('a-paperback', 'paperback')
        self.assertIn('/format/paperback/</loc>', render_sitemap_xml())

    def test_a_free_text_print_type_is_not_listed(self):
        from plugins.installed.seo.services import render_sitemap_xml

        _book('a-report', 'PDF report')
        xml = render_sitemap_xml()
        self.assertNotIn('/format/PDF report/', xml)
        self.assertNotIn('/format/PDF%20report/', xml)

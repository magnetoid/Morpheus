"""Taxonomy pages auto-emit CollectionPage + ItemList JSON-LD."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.book_product.models import BookProduct
from plugins.installed.catalog.models import Product


def _book(slug, sku, **kw):
    p = Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=sku,
        price=Money(Decimal('9.00'), 'USD'),
        product_type='simple',
        status='active',
    )
    return BookProduct.objects.create(product=p, **kw)


class TaxonomyJsonLdTests(TestCase):
    def test_facet_detail_emits_collectionpage(self):
        _book('one', 'O-1', publisher='Acme Press')
        _book('two', 'T-1', publisher='Acme Press')
        r = self.client.get('/publisher/acme-press/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'application/ld+json')
        self.assertContains(r, 'CollectionPage')
        self.assertContains(r, 'ItemList')

    def test_index_page_emits_collectionpage_of_terms(self):
        _book('one', 'O-1', author='Jane Doe')
        _book('two', 'T-1', author='John Roe')
        r = self.client.get('/authors/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'application/ld+json')
        self.assertContains(r, 'CollectionPage')
        self.assertContains(r, 'Jane Doe')

    def test_empty_facet_no_crash(self):
        # No books → no items → tag emits nothing, page still renders.
        r = self.client.get('/authors/')
        self.assertEqual(r.status_code, 200)

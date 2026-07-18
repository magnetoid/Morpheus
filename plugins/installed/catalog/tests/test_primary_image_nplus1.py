"""primary_image must resolve from the prefetch cache — no per-row query.

The product card reads ``product.primary_image`` (twice) for every card on the
PLP/rails. The old property did ``.images.filter(is_primary=True).first()``,
which bypasses ``prefetch_related('images')`` and re-queries per row (the audit's
N+1). The property now iterates the prefetched set in Python: 0 queries after a
prefetch, and behaviour-identical to the old ordering.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductImage


def _product_with_images(slug, n_images, primary_index=None):
    p = Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug.upper(),
        status='active',
        price=Money(Decimal('10'), 'USD'),
    )
    for i in range(n_images):
        ProductImage.objects.create(
            product=p,
            image=f'products/{slug}-{i}.jpg',
            is_primary=(i == primary_index),
            sort_order=i,
        )
    return p


class PrimaryImageNPlusOneTests(TestCase):
    def test_no_query_per_row_after_prefetch(self):
        for i in range(6):
            _product_with_images(f'book-{i}', 3, primary_index=1)
        qs = Product.objects.filter(status='active').prefetch_related('images')
        products = list(qs)  # products + images prefetch — the only queries
        with self.assertNumQueries(0):
            covers = [p.primary_image for p in products]
        # every product resolved a cover, none via a query
        self.assertEqual(len(covers), 6)
        self.assertTrue(all(c is not None for c in covers))

    def test_picks_the_flagged_primary(self):
        p = _product_with_images('flagged', 3, primary_index=2)
        # is_primary image is at sort_order=2; the property must return it
        self.assertTrue(p.primary_image.is_primary)
        self.assertEqual(p.primary_image.sort_order, 2)

    def test_falls_back_to_first_when_no_primary(self):
        p = _product_with_images('no-primary', 3, primary_index=None)
        # no is_primary → lowest sort_order (the model's default ordering)
        self.assertEqual(p.primary_image.sort_order, 0)

    def test_none_when_no_images(self):
        p = Product.objects.create(
            name='Bare', slug='bare', sku='BARE', status='active', price=Money(5, 'USD')
        )
        self.assertIsNone(p.primary_image)

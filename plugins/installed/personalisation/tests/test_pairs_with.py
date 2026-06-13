"""'Pairs with this' — co-purchase + similarity blend, self-excluded."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.personalisation.services import pairs_with


def _product(slug, sku):
    return Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=sku,
        price=Money(Decimal('10.00'), 'USD'),
        product_type='simple',
        status='active',
    )


class PairsWithTests(TestCase):
    def test_returns_copurchase_and_excludes_self(self):
        from plugins.installed.personalisation.models import CoPurchaseScore

        a = _product('anchor', 'AN')
        b = _product('book-b', 'B')
        c = _product('book-c', 'C')
        CoPurchaseScore.objects.create(anchor=a, related=b, score=0.9, co_count=5)
        CoPurchaseScore.objects.create(anchor=a, related=c, score=0.5, co_count=3)

        out = pairs_with(a, request=None, k=10)
        slugs = [p.slug for p in out]
        self.assertIn('book-b', slugs)
        self.assertIn('book-c', slugs)
        self.assertNotIn('anchor', slugs)  # never recommends the product itself

    def test_no_data_returns_empty_or_similar(self):
        a = _product('lonely', 'L')
        # No co-purchase, embeddings may fall back to category/random via similar_to.
        out = pairs_with(a, request=None, k=10)
        self.assertNotIn('lonely', [p.slug for p in out])

    def test_respects_k_limit(self):
        from plugins.installed.personalisation.models import CoPurchaseScore

        a = _product('a2', 'A2')
        for i in range(6):
            r = _product(f'r{i}', f'R{i}')
            CoPurchaseScore.objects.create(anchor=a, related=r, score=0.5, co_count=2)
        out = pairs_with(a, request=None, k=3)
        self.assertLessEqual(len(out), 3)

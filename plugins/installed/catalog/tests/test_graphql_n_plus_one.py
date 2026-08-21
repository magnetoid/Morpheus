"""Product-list N+1 regression (v0.57.0).

`ProductType.collections`/`price`/`priceStartsFrom` did `.filter()`/`.count()`
on relations that `_PRODUCT_PREFETCH` had ALREADY prefetched — which discards
the prefetch cache and re-queries once per product, so a product list's query
count scaled with its length. The resolvers now filter in Python over `.all()`.
The guard: the query count for N products with variants + collections does NOT
grow when N doubles.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from api.client import internal_graphql
from plugins.installed.catalog.models import (
    Collection,
    Product,
    ProductVariant,
)

_Q = """
query { products(first: 50) {
  id name
  price { amount currency }
  priceStartsFrom
  collections { id name }
} }
"""


def _variable_product(i: int, collection: Collection) -> Product:
    p = Product.objects.create(
        name=f'Var {i}',
        slug=f'var-{i}',
        sku=f'VAR-{i}',
        status='active',
        product_type='variable',
        price=Money(Decimal('0.00'), 'USD'),
    )
    ProductVariant.objects.create(
        product=p, name='A', sku=f'VAR-{i}-A', is_active=True, price=Money(Decimal('20.00'), 'USD')
    )
    ProductVariant.objects.create(
        product=p, name='B', sku=f'VAR-{i}-B', is_active=True, price=Money(Decimal('12.00'), 'USD')
    )
    p.collections.add(collection)
    return p


class ProductListNPlusOneTests(TestCase):
    def _count_queries(self, n: int) -> int:
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        Product.objects.all().delete()
        col = Collection.objects.create(name='Feat', slug=f'feat-{n}', is_active=True)
        for i in range(n):
            _variable_product(i, col)
        with CaptureQueriesContext(connection) as ctx:
            internal_graphql(_Q)
        return len(ctx.captured_queries)

    def test_query_count_is_flat_as_products_grow(self):
        few = self._count_queries(2)
        many = self._count_queries(8)
        # A per-product re-query would make `many` ~ 3x `few` (collections +
        # variants price + variants count, each per product). Flat = prefetch
        # cache used. Allow a tiny constant slack.
        self.assertLessEqual(
            many,
            few + 2,
            f'product-list query count grew with N ({few} → {many}) — a resolver '
            f'is re-querying a prefetched relation (N+1).',
        )

"""PRODUCT_STOCK_SUMMARY: the inventory app's answer for surfaces that show
stock without owning it (the marketplace vendor portal).

A product with no stock rows, or with tracking switched off, is untracked and
left out — reporting it as zero would tell a vendor their product is sold out
when nobody counts it at all.
"""

from __future__ import annotations

from django.test import TestCase
from djmoney.money import Money

from morpheus.core import events, hook_registry
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory.models import StockLevel, Warehouse
from plugins.installed.inventory.services import stock_summary


class StockSummaryTests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)

    def _product(self, slug, *, quantities=(), reserved=0, track=True):
        product = Product.objects.create(
            name=slug,
            slug=slug,
            sku=slug.upper(),
            price=Money(10, 'USD'),
            status='active',
            track_inventory=track,
        )
        for i, quantity in enumerate(quantities):
            variant = ProductVariant.objects.create(
                product=product, name=f'V{i}', sku=f'{slug.upper()}-{i}', price=Money(10, 'USD')
            )
            StockLevel.objects.create(
                variant=variant,
                warehouse=self.warehouse,
                quantity=quantity,
                reserved_quantity=reserved,
            )
        return product

    def test_tracked_products_are_summed_and_flagged(self):
        plenty = self._product('plenty', quantities=(10, 15))
        low = self._product('low', quantities=(4,), reserved=1)
        gone = self._product('gone', quantities=(2,), reserved=2)
        answer = stock_summary([plenty.pk, low.pk, gone.pk])
        self.assertEqual(answer[str(plenty.pk)], {'available': 25, 'out': False, 'low': False})
        self.assertEqual(answer[str(low.pk)], {'available': 3, 'out': False, 'low': True})
        self.assertEqual(answer[str(gone.pk)], {'available': 0, 'out': True, 'low': False})

    def test_untracked_products_are_left_out(self):
        no_rows = self._product('no-rows')
        switched_off = self._product('off', quantities=(0,), track=False)
        self.assertEqual(stock_summary([no_rows.pk, switched_off.pk]), {})

    def test_the_hook_answers_with_the_same(self):
        low = self._product('hooked', quantities=(2,))
        answer = hook_registry.filter(
            events.PRODUCT_STOCK_SUMMARY, value={}, product_ids=[str(low.pk)]
        )
        self.assertEqual(answer, {str(low.pk): {'available': 2, 'out': False, 'low': True}})

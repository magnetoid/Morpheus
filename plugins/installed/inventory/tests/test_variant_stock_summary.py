"""VARIANT_STOCK_SUMMARY answers what the order's stock reservation could take
for each variant, so a line the shopper did not pick (a free gift) can be left
out instead of making the reservation refuse the whole checkout."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory.models import StockLevel, Warehouse


class VariantStockSummaryTests(TestCase):
    def setUp(self):
        product = Product.objects.create(
            name='Tote', slug='tote', sku='TOTE', price=Money(Decimal('10'), 'EUR')
        )
        self.tracked = ProductVariant.objects.create(product=product, name='Red', sku='T-RED')
        self.untracked = ProductVariant.objects.create(product=product, name='Blue', sku='T-BLUE')
        main = Warehouse.objects.create(name='Main', code='MAIN')
        closed = Warehouse.objects.create(name='Closed', code='OLD', is_active=False)
        StockLevel.objects.create(
            variant=self.tracked, warehouse=main, quantity=5, reserved_quantity=2
        )
        StockLevel.objects.create(variant=self.tracked, warehouse=closed, quantity=40)

    def _ask(self, *variants):
        return hook_registry.filter(
            MorpheusEvents.VARIANT_STOCK_SUMMARY,
            value={},
            variant_ids=[v.pk for v in variants],
        )

    def test_counts_what_active_warehouses_can_give(self):
        self.assertEqual(self._ask(self.tracked), {str(self.tracked.pk): 3})

    def test_an_untracked_variant_is_left_out_not_zero(self):
        self.assertEqual(self._ask(self.untracked), {})

    def test_a_variant_stocked_only_in_a_closed_warehouse_reads_zero(self):
        level = StockLevel.objects.get(variant=self.tracked, warehouse__code='MAIN')
        level.delete()
        self.assertEqual(self._ask(self.tracked), {str(self.tracked.pk): 0})

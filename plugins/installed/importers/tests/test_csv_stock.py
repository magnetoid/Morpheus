"""The CSV import's optional ``stock`` and ``warehouse_code`` columns (v0.152.0).

The importer fires INVENTORY_SET_STOCK and the inventory app answers, so the
importer imports no inventory code, and with inventory off the products still
import and their stock is left alone."""

from __future__ import annotations

import contextlib

from django.core.cache import cache
from django.test import TestCase

from plugins.installed.importers.adapters.csv_products import (
    CSV_FIELDS,
    CsvProductImporter,
    export_products_csv,
)
from plugins.installed.inventory.models import StockLevel, Warehouse
from plugins.registry import app_registry


@contextlib.contextmanager
def disabled(name: str):
    assert app_registry.is_active(name), f'{name} must ship active for this test'
    app_registry.deactivate(name)
    cache.clear()
    try:
        yield
    finally:
        app_registry.activate(name)
        cache.clear()


def _row(**extra):
    return {'sku': 'CSV-1', 'name': 'Candle', 'price': '9.50', 'status': 'active', **extra}


class CsvStockTests(TestCase):
    def test_the_stock_column_sets_units_on_hand(self):
        summary = CsvProductImporter(rows=[_row(stock='12')]).run()
        self.assertEqual(summary.counts.get('stock_set'), 1)
        level = StockLevel.objects.get()
        self.assertEqual(
            (level.variant.sku, level.warehouse.code, level.quantity), ('CSV-1', 'MAIN', 12)
        )

    def test_a_warehouse_code_picks_the_warehouse(self):
        Warehouse.objects.create(name='Main', code='MAIN', is_default=True)
        Warehouse.objects.create(name='Shop', code='SHOP')
        CsvProductImporter(rows=[_row(stock='4', warehouse_code='shop')]).run()
        self.assertEqual(StockLevel.objects.get().warehouse.code, 'SHOP')

    def test_a_bad_count_is_reported_and_the_product_still_imports(self):
        summary = CsvProductImporter(rows=[_row(stock='lots')]).run()
        self.assertEqual(summary.counts.get('product_upserted'), 1)
        self.assertEqual(summary.counts.get('stock_errored'), 1)
        self.assertFalse(StockLevel.objects.exists())

    def test_an_empty_column_leaves_stock_alone(self):
        summary = CsvProductImporter(rows=[_row(stock='')]).run()
        self.assertNotIn('stock_set', summary.counts)
        self.assertFalse(StockLevel.objects.exists())

    def test_with_inventory_off_the_stock_is_skipped(self):
        with disabled('inventory'):
            summary = CsvProductImporter(rows=[_row(stock='5')]).run()
        self.assertEqual(summary.counts.get('stock_skipped'), 1)
        self.assertFalse(StockLevel.objects.exists())

    def test_the_export_carries_no_stock(self):
        CsvProductImporter(rows=[_row(stock='3')]).run()
        header = export_products_csv().splitlines()[0]
        self.assertNotIn('stock', CSV_FIELDS)
        self.assertNotIn('stock', header)

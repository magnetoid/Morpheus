"""Every stock write goes through ``InventoryService`` (v0.152.0): a movement in
the audit log, never below 0, and the low-stock / out-of-stock events fired
once after commit. Until v0.152.0 those two events had subscribers and no
producer, so nobody was ever told that something ran low."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from djmoney.money import Money

from core.hooks import MorpheusEvents, hook_registry
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory.models import StockLevel, StockMovement, Warehouse
from plugins.installed.inventory.services import (
    InsufficientStockError,
    InventoryService,
    create_warehouse,
    default_warehouse,
)


def _variant(sku='SW-1'):
    product = Product.objects.create(
        name=f'Item {sku}', slug=sku.lower(), sku=f'P-{sku}', status='active', price=10
    )
    return ProductVariant.objects.create(
        product=product, name='Std', sku=sku, price=Money(Decimal('10'), 'USD')
    )


class StockWriteTests(TestCase):
    def setUp(self):
        self.variant = _variant()
        self.main = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)

    def test_setting_a_count_records_a_movement_and_starts_counting(self):
        level = InventoryService.set_quantity(self.variant, self.main, 12, reason='Count')
        self.assertEqual(level.quantity, 12)
        move = StockMovement.objects.get(stock_level=level)
        self.assertEqual(
            (move.movement_type, move.quantity_change, move.quantity_after, move.notes),
            ('adjustment', 12, 12, 'Count'),
        )
        # The same count again changes nothing and records nothing.
        InventoryService.set_quantity(self.variant, self.main, 12)
        self.assertEqual(StockMovement.objects.filter(stock_level=level).count(), 1)

    def test_a_change_never_takes_stock_below_zero(self):
        InventoryService.set_quantity(self.variant, self.main, 3)
        level = InventoryService.adjust(self.variant, self.main, -10)
        self.assertEqual(level.quantity, 0)
        self.assertEqual(StockMovement.objects.filter(stock_level=level).last().quantity_change, 3)

    def test_available_counts_switched_on_warehouses_only(self):
        shop = create_warehouse('Shop floor', 'SHOP')
        InventoryService.set_quantity(self.variant, self.main, 4)
        InventoryService.set_quantity(self.variant, shop, 6)
        self.assertEqual(InventoryService.available(self.variant), 10)
        shop.is_active = False
        shop.save()
        self.assertEqual(InventoryService.available(self.variant), 4)


class TransferTests(TestCase):
    def setUp(self):
        self.variant = _variant('TR-1')
        self.main = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)
        self.shop = Warehouse.objects.create(name='Shop', code='SHOP')
        InventoryService.set_quantity(self.variant, self.main, 10)

    def test_a_transfer_moves_free_units_in_two_movements(self):
        moved = InventoryService.transfer(self.variant, self.main, self.shop, 4, reason='Restock')
        self.assertEqual(moved, 4)
        levels = {sl.warehouse.code: sl.quantity for sl in StockLevel.objects.all()}
        self.assertEqual(levels, {'MAIN': 6, 'SHOP': 4})
        moves = StockMovement.objects.filter(movement_type='transfer')
        self.assertEqual(sorted(m.quantity_change for m in moves), [-4, 4])
        self.assertTrue(all(m.reference == 'Transfer MAIN → SHOP' for m in moves))

    def test_units_held_for_orders_stay_where_they_are(self):
        StockLevel.objects.filter(warehouse=self.main).update(reserved_quantity=8)
        with self.assertRaises(InsufficientStockError):
            InventoryService.transfer(self.variant, self.main, self.shop, 3)
        self.assertEqual(StockLevel.objects.get(warehouse=self.main).quantity, 10)
        self.assertFalse(StockMovement.objects.filter(movement_type='transfer').exists())

    def test_a_transfer_needs_two_warehouses_and_a_unit(self):
        with self.assertRaises(ValueError):
            InventoryService.transfer(self.variant, self.main, self.main, 1)
        with self.assertRaises(ValueError):
            InventoryService.transfer(self.variant, self.main, self.shop, 0)


class LowStockEventTests(TestCase):
    def setUp(self):
        self.variant = _variant('EV-1')
        self.main = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)
        InventoryService.set_quantity(self.variant, self.main, 10)  # reorder point is 5

    def _events(self, write):
        with (
            patch.object(hook_registry, 'fire') as fire,
            self.captureOnCommitCallbacks(execute=True),
        ):
            write()
        return [c.args[0] for c in fire.call_args_list]

    def test_crossing_the_reorder_point_says_so_once(self):
        events = self._events(lambda: InventoryService.adjust(self.variant, self.main, -6))
        self.assertEqual(events, [MorpheusEvents.PRODUCT_LOW_STOCK])
        # Already below the line: a further sale is not news.
        self.assertEqual(
            self._events(lambda: InventoryService.adjust(self.variant, self.main, -1)), []
        )

    def test_reaching_nothing_left_says_out_of_stock(self):
        events = self._events(lambda: InventoryService.set_quantity(self.variant, self.main, 0))
        self.assertEqual(events, [MorpheusEvents.PRODUCT_OUT_OF_STOCK])

    def test_a_delivery_is_not_an_alert(self):
        self.assertEqual(
            self._events(lambda: InventoryService.adjust(self.variant, self.main, 5)), []
        )


class WarehouseHelperTests(TestCase):
    def test_the_first_warehouse_is_the_default_and_codes_are_unique(self):
        first = create_warehouse('North depot')
        self.assertEqual((first.code, first.is_default), ('NORTH-DEPOT', True))
        second = create_warehouse('South', 'south', make_default=True)
        first.refresh_from_db()
        self.assertEqual((first.is_default, second.is_default), (False, True))
        with self.assertRaises(ValueError):
            create_warehouse('Another', 'SOUTH')
        with self.assertRaises(ValueError):
            create_warehouse('  ')

    def test_a_store_with_no_warehouse_gets_main_when_asked(self):
        self.assertIsNone(default_warehouse())
        main = default_warehouse(create=True)
        self.assertEqual((main.code, main.name, main.is_default), ('MAIN', 'Main warehouse', True))
        self.assertEqual(default_warehouse(create=True), main)

"""The Warehouses page (v0.152.0): staff-only, gated on ``inventory.write``, and
every action writes through the inventory service."""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory.models import StockLevel, StockMovement, Warehouse
from plugins.installed.inventory.services import InventoryService

URL = '/dashboard/inventory/warehouses/'


def _user(name, *, staff):
    return get_user_model().objects.create_user(
        username=name, email=f'{name}@example.test', password='x', is_staff=staff
    )


class WarehousesPageGateTests(TestCase):
    def test_a_visitor_is_sent_to_sign_in(self):
        response = Client().get(URL)
        self.assertEqual(response.status_code, 302)

    def test_a_customer_is_turned_away(self):
        client = Client()
        client.force_login(_user('shopper', staff=False))
        self.assertIn(client.get(URL).status_code, (302, 403))

    def test_staff_without_inventory_write_is_refused_when_roles_are_enforced(self):
        client = Client()
        client.force_login(_user('clerk', staff=True))
        with (
            patch('core.authz.enforcement_mode', return_value='enforce'),
            patch('core.authz.has_capability', return_value=False),
        ):
            self.assertEqual(client.get(URL).status_code, 403)

    def test_staff_with_inventory_write_see_the_page(self):
        client = Client()
        client.force_login(_user('manager', staff=True))
        response = client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Add a warehouse', response.content.decode())


class WarehousesPageActionTests(TestCase):
    def setUp(self):
        self.client.force_login(_user('owner', staff=True))
        self.main = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)

    def _post(self, **data):
        return self.client.post(URL, data)

    def test_add_edit_and_make_default(self):
        self._post(action='create', name='Shop floor', code='')
        shop = Warehouse.objects.get(code='SHOP-FLOOR')
        self.assertFalse(shop.is_default)
        self._post(action='edit', warehouse_id=shop.pk, name='Shop', code='shop')
        shop.refresh_from_db()
        self.assertEqual((shop.name, shop.code), ('Shop', 'SHOP'))
        self._post(action='default', warehouse_id=shop.pk)
        self.main.refresh_from_db()
        shop.refresh_from_db()
        self.assertEqual((self.main.is_default, shop.is_default), (False, True))

    def test_a_code_is_never_taken_twice(self):
        self._post(action='create', name='Another main', code='main')
        self.assertEqual(Warehouse.objects.filter(code='MAIN').count(), 1)

    def test_switching_off_and_on(self):
        self._post(action='toggle', warehouse_id=self.main.pk)
        self.main.refresh_from_db()
        self.assertEqual((self.main.is_active, self.main.is_default), (False, False))
        self._post(action='toggle', warehouse_id=self.main.pk)
        self.main.refresh_from_db()
        self.assertTrue(self.main.is_active)

    def test_a_warehouse_with_stock_records_is_never_deleted(self):
        product = Product.objects.create(name='Mug', slug='mug', sku='MUG', price=5)
        variant = ProductVariant.objects.create(product=product, name='Default', sku='MUG')
        InventoryService.set_quantity(variant, self.main, 0)
        StockLevel.objects.get_or_create(variant=variant, warehouse=self.main)
        self._post(action='delete', warehouse_id=self.main.pk)
        self.assertTrue(Warehouse.objects.filter(pk=self.main.pk).exists())
        empty = Warehouse.objects.create(name='Empty', code='EMPTY')
        self._post(action='delete', warehouse_id=empty.pk)
        self.assertFalse(Warehouse.objects.filter(pk=empty.pk).exists())

    def test_moving_stock_from_the_page(self):
        shop = Warehouse.objects.create(name='Shop', code='SHOP')
        product = Product.objects.create(name='Mug', slug='mug', sku='MUG', price=5)
        variant = ProductVariant.objects.create(product=product, name='Default', sku='MUG')
        InventoryService.set_quantity(variant, self.main, 10)
        self._post(action='transfer', sku='mug', from_id=self.main.pk, to_id=shop.pk, quantity='3')
        levels = {sl.warehouse.code: sl.quantity for sl in StockLevel.objects.all()}
        self.assertEqual(levels, {'MAIN': 7, 'SHOP': 3})
        move = StockMovement.objects.filter(movement_type='transfer', quantity_change=3).get()
        self.assertEqual(move.created_by.username, 'owner')
        page = self.client.get(URL).content.decode()
        self.assertIn('Move stock between warehouses', page)
        self.assertIn('Warehouse Transfer', page)

    def test_moving_more_than_is_free_says_why(self):
        shop = Warehouse.objects.create(name='Shop', code='SHOP')
        product = Product.objects.create(name='Mug', slug='mug', sku='MUG', price=5)
        variant = ProductVariant.objects.create(product=product, name='Default', sku='MUG')
        InventoryService.set_quantity(variant, self.main, 2)
        response = self._post(
            action='transfer', sku='MUG', from_id=self.main.pk, to_id=shop.pk, quantity='5'
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(StockLevel.objects.get(warehouse=self.main).quantity, 2)
        self.assertIn('2 free to move', self.client.get(URL).content.decode())

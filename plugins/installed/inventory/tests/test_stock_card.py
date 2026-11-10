"""The Stock card on the dashboard's product form (v0.152.0): units on hand per
variant and warehouse, and backorders. Until v0.152.0 no dashboard page could
enter a stock count at all."""

from __future__ import annotations

import contextlib

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import QueryDict
from django.test import TestCase

from core.hooks import MorpheusEvents, hook_registry
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory import stock_card
from plugins.installed.inventory.models import StockLevel, StockMovement, Warehouse
from plugins.registry import app_registry

TEMPLATE = 'inventory/blocks/product_stock_card.html'


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


def _post(data: dict, lists: dict | None = None) -> QueryDict:
    post = QueryDict(mutable=True)
    post.update(data)
    for key, values in (lists or {}).items():
        post.setlist(key, values)
    return post


class StockCardContextTests(TestCase):
    def test_a_download_or_a_booking_has_no_card(self):
        for kind in ('digital', 'service'):
            product = Product.objects.create(
                name=kind, slug=f'k-{kind}', sku=f'K-{kind}', price=5, product_type=kind
            )
            self.assertIsNone(stock_card.card(product))

    def test_a_one_form_product_in_a_new_store_shows_one_box(self):
        product = Product.objects.create(name='Mug', slug='mug', sku='MUG', price=5)
        ctx = stock_card.card(product)
        self.assertEqual([c['name'] for c in ctx['stock_columns']], ['Main warehouse'])
        self.assertEqual([r['key'] for r in ctx['stock_rows']], ['new'])
        self.assertEqual(ctx['stock_rows'][0]['cells'][0]['name'], 'stock__new__new')

    def test_each_variant_gets_a_row_and_each_warehouse_a_column(self):
        product = Product.objects.create(
            name='Tee', slug='tee', sku='TEE', price=5, product_type='variable'
        )
        small = ProductVariant.objects.create(product=product, name='S', sku='TEE-S')
        ProductVariant.objects.create(product=product, name='M', sku='TEE-M')
        ProductVariant.objects.create(
            product=product, name='PDF', sku='TEE-D', variant_type='digital'
        )
        main = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)
        Warehouse.objects.create(name='Shop', code='SHOP')
        Warehouse.objects.create(name='Old', code='OLD', is_active=False)
        StockLevel.objects.create(variant=small, warehouse=main, quantity=7, reserved_quantity=2)
        ctx = stock_card.card(product)
        self.assertEqual([c['name'] for c in ctx['stock_columns']], ['Main', 'Shop'])
        self.assertEqual([r['sku'] for r in ctx['stock_rows']], ['TEE-S', 'TEE-M'])
        self.assertEqual(ctx['stock_rows'][0]['cells'][0]['value'], 7)
        self.assertEqual(ctx['stock_rows'][0]['reserved'], 2)
        self.assertTrue(ctx['stock_own_toggle'])


class StockCardSaveTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(name='Mug', slug='mug', sku='MUG', price=5)

    def _save(self, data, lists=None):
        hook_registry.fire(
            MorpheusEvents.PRODUCT_FORM_SAVED, product=self.product, post=_post(data, lists)
        )

    def test_the_first_count_makes_the_default_variant_and_main_warehouse(self):
        self._save({'stock_submitted': '1', 'stock__new__new': '9'}, {'stock_rows': ['new']})
        variant = self.product.variants.get()
        self.assertEqual((variant.name, variant.sku), ('Default', 'MUG'))
        level = StockLevel.objects.get(variant=variant)
        self.assertEqual((level.warehouse.code, level.quantity), ('MAIN', 9))
        self.assertEqual(StockMovement.objects.get().notes, 'Set on the product page')

    def test_an_empty_box_or_a_form_without_the_card_leaves_stock_alone(self):
        self._save({'stock_submitted': '1', 'stock__new__new': '4'}, {'stock_rows': ['new']})
        variant = self.product.variants.get()
        main = Warehouse.objects.get()
        key = f'stock__{variant.pk}__{main.pk}'
        self._save({'stock_submitted': '1', key: ''}, {'stock_rows': [str(variant.pk)]})
        self._save({'name': 'A form without the card', key: '0'})
        self.assertEqual(StockLevel.objects.get(variant=variant).quantity, 4)

    def test_the_backorders_box_sets_the_policy(self):
        variant = ProductVariant.objects.create(product=self.product, name='Default', sku='MUG')
        key = str(variant.pk)
        self._save({'stock_submitted': '1', f'backorder__{key}': 'on'}, {'stock_rows': [key]})
        variant.refresh_from_db()
        self.assertEqual(variant.inventory_policy, 'continue')
        self._save({'stock_submitted': '1'}, {'stock_rows': [key]})
        variant.refresh_from_db()
        self.assertEqual(variant.inventory_policy, 'deny')

    def test_a_variable_product_carries_its_own_tracking_box(self):
        product = Product.objects.create(
            name='Tee', slug='tee', sku='TEE', price=5, product_type='variable'
        )
        hook_registry.fire(
            MorpheusEvents.PRODUCT_FORM_SAVED,
            product=product,
            post=_post({'stock_submitted': '1', 'stock_track_submitted': '1'}),
        )
        product.refresh_from_db()
        self.assertFalse(product.track_inventory)
        # A one-form product's tracking box is the shell's: the card never touches it.
        self._save({'stock_submitted': '1', 'stock_track_submitted': '1'})
        self.product.refresh_from_db()
        self.assertTrue(self.product.track_inventory)


class StockCardOnTheProductPageTests(TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            username='stock-staff', email='stock@example.test', password='x', is_staff=True
        )
        self.client.force_login(staff)
        self.product = Product.objects.create(name='Mug', slug='mug', sku='MUG', price=5)

    def test_the_product_page_shows_the_card_while_inventory_is_on(self):
        url = f'/dashboard/products/{self.product.pk}/'
        self.assertIn('id="stock-card"', self.client.get(url).content.decode())
        with disabled('inventory'):
            cards = hook_registry.filter(
                MorpheusEvents.PRODUCT_FORM_CARDS, value=[], product=self.product
            )
            self.assertNotIn(TEMPLATE, [c.get('template') for c in cards])

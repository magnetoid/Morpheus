"""Linda's stock tools and the GraphQL stock mutations write through the
inventory service (v0.152.0). agent_core's ``inventory.set_stock`` and both
mutations used to write the stock row directly: no movement, no alert."""

from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.agents.registry import agent_registry
from morpheus.core import ToolError
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory.models import StockLevel, StockMovement, Warehouse

WRITES = (
    'inventory.set_stock',
    'inventory.adjust_stock',
    'inventory.transfer_stock',
    'inventory.create_warehouse',
)


def _run(tool, **args):
    return agent_registry.get_tool(tool).invoke(args)


class StockToolTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(name='Mug', slug='mug', sku='MUG', price=5)

    def test_the_inventory_app_owns_every_stock_tool_and_each_write_asks_first(self):
        for name in (*WRITES, 'inventory.stock_levels', 'inventory.warehouses'):
            with self.subTest(name):
                self.assertEqual(agent_registry._tool_owners.get(name), 'inventory')
        for name in WRITES:
            tool = agent_registry.get_tool(name)
            self.assertTrue(tool.requires_approval, name)
            self.assertIn('inventory.write', tool.scopes)

    def test_set_stock_counts_a_one_form_product_from_its_slug(self):
        _run('inventory.set_stock', sku='mug', quantity=6)
        level = StockLevel.objects.get()
        self.assertEqual(
            (level.variant.name, level.warehouse.code, level.quantity), ('Default', 'MAIN', 6)
        )
        self.assertEqual(StockMovement.objects.get().notes, 'Set by Linda')

    def test_set_stock_still_takes_the_old_argument_names(self):
        Warehouse.objects.create(name='Main', code='MAIN', is_default=True)
        shop = Warehouse.objects.create(name='Shop floor', code='SHOP')
        variant = ProductVariant.objects.create(product=self.product, name='Default', sku='MUG-1')
        _run('inventory.set_stock', variant_sku='MUG-1', quantity=3, warehouse='Shop floor')
        self.assertEqual(StockLevel.objects.get(variant=variant, warehouse=shop).quantity, 3)
        _run('inventory.set_stock', product_slug='mug', quantity=4)
        self.assertEqual(
            StockLevel.objects.get(variant=variant, warehouse__code='MAIN').quantity, 4
        )

    def test_a_product_with_several_variants_needs_the_variant_sku(self):
        ProductVariant.objects.create(product=self.product, name='S', sku='MUG-S')
        ProductVariant.objects.create(product=self.product, name='L', sku='MUG-L')
        with self.assertRaises(ToolError):
            _run('inventory.set_stock', sku='mug', quantity=1)
        self.assertFalse(StockLevel.objects.exists())

    def test_transfer_and_create_warehouse(self):
        _run('inventory.create_warehouse', name='Main')
        _run('inventory.create_warehouse', name='Shop')
        _run('inventory.set_stock', sku='mug', quantity=5)
        _run('inventory.transfer_stock', sku='mug', from_code='main', to_code='SHOP', quantity=2)
        levels = {sl.warehouse.code: sl.quantity for sl in StockLevel.objects.all()}
        self.assertEqual(levels, {'MAIN': 3, 'SHOP': 2})
        out = _run('inventory.stock_levels', sku='mug').output
        self.assertEqual(sum(r['free'] for r in out['levels']), 5)


class StockMutationTests(TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            username='api-staff', email='api@example.test', password='x', is_staff=True
        )
        self.client.force_login(staff)
        product = Product.objects.create(name='Mug', slug='mug', sku='MUG', price=5)
        self.variant = ProductVariant.objects.create(product=product, name='Default', sku='MUG-1')

    def _gql(self, query):
        response = self.client.post(
            '/graphql/', json.dumps({'query': query}), content_type='application/json'
        )
        return response.json()['data']

    def test_set_and_adjust_leave_movements(self):
        data = self._gql(
            'mutation { setStock(input: {variantSku: "MUG-1", quantity: 5}) { quantity error } }'
        )
        self.assertEqual(data['setStock'], {'quantity': 5, 'error': ''})
        data = self._gql(
            'mutation { adjustStock(input: {productSlug: "mug", delta: -2}) { quantity error } }'
        )
        self.assertEqual(data['adjustStock'], {'quantity': 3, 'error': ''})
        self.assertEqual(
            list(
                StockMovement.objects.order_by('created_at').values_list('quantity_change', 'notes')
            ),
            [(5, 'Set over the API'), (-2, 'Changed over the API')],
        )

    def test_adjust_still_refuses_to_go_below_zero(self):
        self._gql('mutation { setStock(input: {variantSku: "MUG-1", quantity: 1}) { quantity } }')
        data = self._gql(
            'mutation { adjustStock(input: {variantSku: "MUG-1", delta: -3}) { quantity error } }'
        )
        self.assertIn('below zero', data['adjustStock']['error'])
        self.assertEqual(StockLevel.objects.get().quantity, 1)

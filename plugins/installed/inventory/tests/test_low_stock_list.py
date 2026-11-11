"""What is running low (v0.152.1): one list, on the Warehouses page, that the
dashboard home and Pulse read too. Pulse used to link the low-stock card to
``/dashboard/inventory/?filter=low_stock``, a page that never existed."""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory.models import StockLevel, Warehouse
from plugins.installed.inventory.services import low_stock_levels

URL = '/dashboard/inventory/warehouses/'


def _variant(slug, *, tracked=True):
    product = Product.objects.create(
        name=slug.title(), slug=slug, sku=slug.upper(), price=5, track_inventory=tracked
    )
    return ProductVariant.objects.create(product=product, name='Default', sku=slug.upper())


class LowStockListTests(TestCase):
    def setUp(self):
        self.main = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)
        closed = Warehouse.objects.create(name='Closed', code='OLD', is_active=False)
        self.low = _variant('lantern')
        StockLevel.objects.create(
            variant=self.low, warehouse=self.main, quantity=6, reserved_quantity=3
        )
        StockLevel.objects.create(variant=_variant('rope'), warehouse=self.main, quantity=40)
        StockLevel.objects.create(variant=_variant('poster', tracked=False), warehouse=self.main)
        StockLevel.objects.create(variant=_variant('tarp'), warehouse=closed)

    def test_free_units_at_or_below_the_threshold_in_open_warehouses_of_counted_products(self):
        self.assertEqual([sl.variant_id for sl in low_stock_levels()], [self.low.pk])

    def test_the_warehouses_page_lists_them_with_a_link_to_the_stock_card(self):
        self.client.force_login(
            get_user_model().objects.create_user(
                username='owner', email='owner@example.test', password='x', is_staff=True
            )
        )
        page = self.client.get(URL).content.decode()
        self.assertIn('id="low-stock"', page)
        self.assertIn(f'/dashboard/products/{self.low.product_id}/#stock-card', page)
        self.assertNotIn('Rope', page.split('id="low-stock"')[1].split('Recent stock changes')[0])

    def test_pulse_counts_the_same_list_and_links_to_it(self):
        from plugins.installed.ai_assistant.services import pulse

        card = pulse._low_stock_signal()
        self.assertTrue(card['title'].startswith('1 SKU'))
        self.assertIn('Lantern (3)', card['body'])
        url = card['suggested_action']['url']
        self.assertEqual(url, f'{URL}#low-stock')
        self.assertEqual(resolve(url.split('#')[0]).url_name, 'warehouses')

    def test_pulse_says_nothing_while_inventory_is_off(self):
        from plugins.installed.ai_assistant.services import pulse
        from plugins.registry import app_registry

        real = app_registry.is_active
        with patch.object(
            app_registry, 'is_active', side_effect=lambda n: n != 'inventory' and real(n)
        ):
            self.assertIsNone(pulse._low_stock_signal())

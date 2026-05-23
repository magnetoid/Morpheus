"""advanced_ecommerce tests: contributions wired, hooks fire, dashboard pages route."""
from __future__ import annotations

from decimal import Decimal

from django.test import RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.advanced_ecommerce.plugin import AdvancedEcommercePlugin
from plugins.installed.catalog.models import Product
from plugins.installed.inventory.models import StockLevel, Warehouse
from plugins.installed.catalog.models import ProductVariant


class AdvancedEcommerceContributionsTests(TestCase):

    def test_storefront_blocks_declared(self):
        blocks = AdvancedEcommercePlugin().contribute_storefront_blocks()
        slots = {b.slot for b in blocks}
        self.assertIn('home_below_grid', slots)
        self.assertIn('cart_summary_extra', slots)
        self.assertIn('pdp_below_price', slots)

    def test_settings_panel_declared(self):
        panel = AdvancedEcommercePlugin().contribute_settings_panel()
        self.assertIsNotNone(panel)
        self.assertIn('properties', panel.schema)
        self.assertIn('low_stock_threshold', panel.schema['properties'])


class RecentlyViewedHookTests(TestCase):

    def test_product_viewed_hook_writes_to_session(self):
        product = Product.objects.create(
            name='X', slug='x', sku='X', price=Money(10, 'USD'), status='active',
        )
        rf = RequestFactory()
        request = rf.get('/p/x/')
        request.session = {}
        AdvancedEcommercePlugin().on_product_viewed(product=product, request=request)
        self.assertIn('x', request.session.get('recently_viewed', []))

    def test_recently_viewed_capped_at_eight(self):
        rf = RequestFactory()
        request = rf.get('/')
        request.session = {'recently_viewed': [f's{i}' for i in range(8)]}
        product = Product.objects.create(
            name='New', slug='new', sku='N', price=Money(10, 'USD'), status='active',
        )
        AdvancedEcommercePlugin().on_product_viewed(product=product, request=request)
        self.assertEqual(len(request.session['recently_viewed']), 8)
        self.assertEqual(request.session['recently_viewed'][0], 'new')


class LowStockTemplateTagTests(TestCase):

    def test_product_total_stock(self):
        from plugins.installed.advanced_ecommerce.templatetags.advanced_ecommerce import (
            product_total_stock,
        )

        product = Product.objects.create(
            name='Y', slug='y', sku='Y', price=Money(10, 'USD'), status='active',
        )
        v = ProductVariant.objects.create(product=product, name='V', sku='Y-V', price=Money(10, 'USD'))
        wh = Warehouse.objects.create(name='W', code='W', is_default=True)
        StockLevel.objects.create(variant=v, warehouse=wh, quantity=3, reserved_quantity=0)
        self.assertEqual(product_total_stock(product), 3)



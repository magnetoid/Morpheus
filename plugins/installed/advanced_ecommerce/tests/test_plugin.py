"""advanced_ecommerce tests: contributions wired, hooks fire, dashboard pages route."""

# ruff: noqa: PLC0415

from __future__ import annotations

from django.test import RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.advanced_ecommerce.plugin import AdvancedEcommercePlugin
from plugins.installed.advanced_ecommerce.templatetags.advanced_ecommerce import (
    featured_collection_rails,
)
from plugins.installed.catalog.models import Collection, Product, ProductVariant
from plugins.installed.inventory.models import StockLevel, Warehouse


class AdvancedEcommerceContributionsTests(TestCase):
    def test_storefront_blocks_declared(self):
        blocks = AdvancedEcommercePlugin().contribute_storefront_blocks()
        slots = {b.slot for b in blocks}
        self.assertIn('home_after_rails', slots)
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
            name='X',
            slug='x',
            sku='X',
            price=Money(10, 'USD'),
            status='active',
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
            name='New',
            slug='new',
            sku='N',
            price=Money(10, 'USD'),
            status='active',
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
            name='Y',
            slug='y',
            sku='Y',
            price=Money(10, 'USD'),
            status='active',
        )
        v = ProductVariant.objects.create(
            product=product, name='V', sku='Y-V', price=Money(10, 'USD')
        )
        wh = Warehouse.objects.create(name='W', code='W', is_default=True)
        StockLevel.objects.create(variant=v, warehouse=wh, quantity=3, reserved_quantity=0)
        self.assertEqual(product_total_stock(product), 3)


class CollectionRailsTests(TestCase):
    """featured_collection_rails powers the homepage collection sliders."""

    def _product(self, slug):
        return Product.objects.create(
            name=slug,
            slug=slug,
            sku=slug.upper(),
            price=Money(8, 'USD'),
            status='active',
        )

    def test_featured_collection_with_products_is_a_rail(self):
        c = Collection.objects.create(
            name='Spring', slug='spring', is_active=True, is_featured=True
        )
        c.products.add(self._product('a'), self._product('b'))
        rails = featured_collection_rails()
        self.assertEqual(len(rails), 1)
        self.assertEqual(rails[0]['collection'].slug, 'spring')
        self.assertEqual(len(rails[0]['products']), 2)

    def test_non_featured_and_empty_collections_excluded(self):
        # Featured but empty → excluded.
        Collection.objects.create(name='Empty', slug='empty', is_active=True, is_featured=True)
        # Has a product but not featured → excluded.
        plain = Collection.objects.create(
            name='Plain', slug='plain', is_active=True, is_featured=False
        )
        plain.products.add(self._product('p'))
        self.assertEqual(featured_collection_rails(), [])

    def test_exclude_slug_skips_the_staff_picks_collection(self):
        for slug in ('staff', 'other'):
            c = Collection.objects.create(name=slug, slug=slug, is_active=True, is_featured=True)
            c.products.add(self._product(f'{slug}-1'))
        rails = featured_collection_rails(exclude_slug='staff')
        self.assertEqual([r['collection'].slug for r in rails], ['other'])

    def test_disabled_via_config_returns_empty(self):
        c = Collection.objects.create(
            name='Spring', slug='spring', is_active=True, is_featured=True
        )
        c.products.add(self._product('a'))
        from plugins.registry import plugin_registry

        plugin = plugin_registry.get('advanced_ecommerce')
        plugin.set_config('enable_collection_rails', False)
        try:
            self.assertEqual(featured_collection_rails(), [])
        finally:
            plugin.set_config('enable_collection_rails', True)

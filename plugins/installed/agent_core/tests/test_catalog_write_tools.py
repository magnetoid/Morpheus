"""agent_core's catalog write tools, called the way every agent path calls them.

Linda (MCP edge), the Worker (AgentRuntime) and MCP tokens all go through
``Tool.invoke``. The update/create tools take their optional fields as
``**fields``, which ``invoke`` used to drop — so they reported "Updated" while
changing nothing. Making them work must not open a second, ungated price path:
``products.update_price`` carries the approval gate and the merchant's
per-action price cap, so a price edit here is refused and pointed there.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from morpheus.core import ToolError, agent_registry


class CatalogWriteToolTests(TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Product, ProductVariant

        self.product = Product.objects.create(
            name='Book',
            slug='book',
            sku='B1',
            price=Money(Decimal('10.00'), 'USD'),
            status='active',
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name='Paperback',
            sku='B1-PB',
            price=Money(Decimal('12.00'), 'USD'),
        )

    def _invoke(self, name, args):
        return agent_registry.get_tool(name).invoke(args, agent=None, context={'source': 'mcp'})

    def test_update_product_applies_the_fields_it_is_given(self):
        self._invoke('catalog.update_product', {'slug': 'book', 'description': 'New copy'})
        self.product.refresh_from_db()
        self.assertEqual(self.product.description, 'New copy')

    def test_update_variant_applies_the_fields_it_is_given(self):
        self._invoke('catalog.update_variant', {'sku': 'B1-PB', 'barcode': '978000'})
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.barcode, '978000')

    def test_create_product_keeps_its_optional_fields(self):
        out = self._invoke(
            'catalog.create_product',
            {'name': 'Second', 'price_amount': '5.00', 'description': 'Body', 'sku': 'S-2'},
        ).output
        from plugins.installed.catalog.models import Product

        created = Product.objects.get(slug=out['slug'])
        self.assertEqual(created.description, 'Body')
        self.assertEqual(created.sku, 'S-2')

    def test_update_product_refuses_a_price_change(self):
        with self.assertRaises(ToolError) as cm:
            self._invoke('catalog.update_product', {'slug': 'book', 'price_amount': '1.00'})
        self.assertIn('products.update_price', str(cm.exception))
        self.product.refresh_from_db()
        self.assertEqual(self.product.price.amount, Decimal('10.00'))

    def test_update_variant_refuses_a_price_change(self):
        with self.assertRaises(ToolError) as cm:
            self._invoke('catalog.update_variant', {'sku': 'B1-PB', 'price_amount': '1.00'})
        self.assertIn('products.update_price', str(cm.exception))
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.price.amount, Decimal('12.00'))

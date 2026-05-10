"""Hard-gate enforcement on destructive Linda tools."""
from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money


class HardGateSmoke(TestCase):
    def test_metafields_delete_refuses_without_ack(self):
        from plugins.installed.catalog.models import Product
        product = Product.objects.create(
            name='Test', slug='hg-test', sku='HG-1', status='active',
            price=Money(Decimal('10.00'), 'USD'),
        )
        from plugins.installed.metafields.models import Metafield
        Metafield.objects.set(product, namespace='book', key='isbn',
                              value='123')
        from core.assistant.tools.ecommerce_writes import metafields_delete_tool
        # confirmed=True alone is not enough — needs hard_gate_ack + echo.
        result = metafields_delete_tool.invoke(
            {'model': 'catalog.Product', 'object_id': str(product.pk),
             'key': 'isbn', 'namespace': 'book', 'confirmed': True},
        )
        self.assertIn('error', getattr(result, 'output', {}) or {})

    def test_metafields_delete_passes_with_ack_and_echo(self):
        from plugins.installed.catalog.models import Product
        product = Product.objects.create(
            name='Test', slug='hg-test-2', sku='HG-2', status='active',
            price=Money(Decimal('10.00'), 'USD'),
        )
        from plugins.installed.metafields.models import Metafield
        Metafield.objects.set(product, namespace='book', key='isbn',
                              value='123')
        from core.assistant.tools.ecommerce_writes import metafields_delete_tool
        result = metafields_delete_tool.invoke(
            {'model': 'catalog.Product', 'object_id': str(product.pk),
             'key': 'isbn', 'namespace': 'book', 'confirmed': True,
             'hard_gate_ack': 'YES', 'echo': 'isbn'},
        )
        self.assertEqual((result.output or {}).get('deleted'), 1)
        self.assertFalse(
            Metafield.objects.filter(namespace='book', key='isbn').exists()
        )

    def test_plugins_disable_refuses_without_echo(self):
        from core.assistant.tools.plugins import disable_plugin_tool
        result = disable_plugin_tool.invoke(
            {'name': 'reviews', 'hard_gate_ack': 'YES', 'echo': 'wrong'},
        )
        out = getattr(result, 'output', {}) or {}
        self.assertIn('error', out)

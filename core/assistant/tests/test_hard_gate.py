"""Hard-gate enforcement on destructive Linda tools."""

# Lazy imports inside test methods are intentional (plugin load-order isolation).
# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money


class HardGateSmoke(TestCase):
    def test_metafields_delete_refuses_without_ack(self):
        from plugins.installed.catalog.models import Product

        product = Product.objects.create(
            name='Test',
            slug='hg-test',
            sku='HG-1',
            status='active',
            price=Money(Decimal('10.00'), 'USD'),
        )
        from plugins.installed.metafields.models import Metafield

        Metafield.objects.set(product, namespace='book', key='isbn', value='123')

        from plugins.installed.metafields.agent_tools import metafields_delete_tool
        from core.assistant.tools.filesystem import ToolError

        # confirmed=True alone is not enough — a refusal RAISES ToolError (the
        # runtime catches it and surfaces the message to the LLM).
        with self.assertRaises(ToolError):
            metafields_delete_tool.invoke(
                {
                    'model': 'catalog.Product',
                    'object_id': str(product.pk),
                    'key': 'isbn',
                    'namespace': 'book',
                    'confirmed': True,
                },
            )

    def test_metafields_delete_passes_with_ack_and_echo(self):
        from plugins.installed.catalog.models import Product

        product = Product.objects.create(
            name='Test',
            slug='hg-test-2',
            sku='HG-2',
            status='active',
            price=Money(Decimal('10.00'), 'USD'),
        )
        from plugins.installed.metafields.models import Metafield

        Metafield.objects.set(product, namespace='book', key='isbn', value='123')

        from plugins.installed.metafields.agent_tools import metafields_delete_tool

        result = metafields_delete_tool.invoke(
            {
                'model': 'catalog.Product',
                'object_id': str(product.pk),
                'key': 'isbn',
                'namespace': 'book',
                'confirmed': True,
                'hard_gate_ack': 'YES',
                'echo': 'isbn',
            },
        )
        self.assertEqual((result.output or {}).get('deleted'), 1)
        self.assertFalse(Metafield.objects.filter(namespace='book', key='isbn').exists())

    def test_plugins_disable_refuses_without_echo(self):
        from core.assistant.tools.filesystem import ToolError
        from core.assistant.tools.plugins import disable_plugin_tool

        # echo mismatch → refusal raises ToolError.
        with self.assertRaises(ToolError):
            disable_plugin_tool.invoke(
                {'name': 'reviews', 'hard_gate_ack': 'YES', 'echo': 'wrong'},
            )

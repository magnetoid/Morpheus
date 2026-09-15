"""Agent-tool contribution + gating for the orders plugin.

``orders.update_status`` / ``cancel`` / ``add_note`` / ``refund`` were migrated
here from core/assistant/tools/{ecommerce_writes,admin_ops}.py (the core→plugin
boundary refactor, Phase 1). These tests lock the migration: the tools surface
to both the agent registry and Linda's catalogue, keep their approval/staging/
hard-gate flags, and ``orders.cancel`` is owned solely by the orders plugin —
agent_core's thinner duplicate was retired, so the name-keyed registry resolves
to the richer confirmed+staging version (and a disable drops it via drop_plugin).
"""

from __future__ import annotations

from django.test import TestCase

from morpheus.core import ToolError, agent_registry

_MIGRATED = ('orders.update_status', 'orders.cancel', 'orders.add_note', 'orders.refund')


class OrdersAgentToolMigrationTests(TestCase):
    def test_migrated_tools_registered_and_owned_by_orders(self):
        for name in _MIGRATED:
            t = agent_registry.get_tool(name)
            self.assertIsNotNone(t, f'{name} not registered')
            self.assertEqual(t.plugin, 'orders', f'{name} owned by {t.plugin!r}, expected orders')

    def test_orders_cancel_collision_resolved_to_orders(self):
        # The name-keyed registry (last-write-wins) previously had a second
        # 'orders.cancel' in agent_core (thin: no staging/confirm). That copy was
        # retired, so the resolved tool must be the orders-owned rich version —
        # and disable-safety follows (drop_plugin('orders') removes it).
        t = agent_registry.get_tool('orders.cancel')
        self.assertEqual(t.plugin, 'orders')
        self.assertTrue(t.supports_staging, 'resolved orders.cancel is the thin agent_core copy')

    def test_surfaced_to_linda_by_name(self):
        from core.assistant.tools import get_default_tools

        names = {t.name for t in get_default_tools()}
        for name in _MIGRATED:
            self.assertIn(name, names, f'{name} missing from Linda catalogue (_migrated_names)')

    def test_surfaced_to_worker_via_scope(self):
        worker = agent_registry.get_agent('worker')
        names = {t.name for t in worker.get_tools()}
        for name in _MIGRATED:
            self.assertIn(name, names, f'{name} not resolvable by the Worker')

    def test_flags_preserved(self):
        for name in ('orders.update_status', 'orders.cancel', 'orders.add_note'):
            t = agent_registry.get_tool(name)
            self.assertTrue(t.requires_approval, f'{name} lost requires_approval')
            self.assertTrue(t.supports_staging, f'{name} lost supports_staging')
        refund = agent_registry.get_tool('orders.refund')
        self.assertTrue(refund.requires_approval)
        self.assertFalse(refund.supports_staging)  # hard-gated, not staged


class OrdersRefundGateTests(TestCase):
    """Ported from core/assistant/tests/test_admin_ops.py with the tool."""

    def test_hard_gate_required(self):
        from plugins.installed.orders.agent_tools import refund_order_tool

        # confirmed alone is not enough — refunds move money (need ack + echo).
        with self.assertRaises(ToolError):
            refund_order_tool.invoke({'order_number': 'X1', 'confirmed': True})

    def test_unknown_order_after_gate(self):
        from plugins.installed.orders.agent_tools import refund_order_tool

        with self.assertRaises(ToolError):
            refund_order_tool.invoke(
                {'order_number': 'nope', 'confirmed': True, 'hard_gate_ack': 'YES', 'echo': 'nope'}
            )


class AnalyticsCurrencyTests(TestCase):
    def test_summary_and_top_products_name_the_currency(self):
        from djmoney.money import Money

        from plugins.installed.orders.agent_tools import (
            analytics_summary_tool,
            analytics_top_products_tool,
        )
        from plugins.installed.orders.models import Order

        Order.objects.create(email='a@example.com', subtotal=Money(9, 'EUR'), total=Money(9, 'EUR'))
        self.assertEqual(analytics_summary_tool.invoke({}).output['currency'], 'EUR')
        self.assertIn('currency', analytics_top_products_tool.invoke({}).output)
        Order.objects.create(email='b@example.com', subtotal=Money(5, 'USD'), total=Money(5, 'USD'))
        self.assertTrue(analytics_summary_tool.invoke({}).output['currency'].startswith('mixed'))


class OrdersGetLineProductTests(TestCase):
    def test_order_lines_name_their_product(self):
        from djmoney.money import Money

        from plugins.installed.catalog.models import Product
        from plugins.installed.orders.agent_tools import orders_get_tool
        from plugins.installed.orders.models import Order, OrderItem

        product = Product.objects.create(
            name='Emma', slug='emma', sku='PG-158', price=Money(8, 'USD')
        )
        order = Order.objects.create(
            email='a@example.com', subtotal=Money(8, 'USD'), total=Money(8, 'USD')
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name='Emma',
            sku='emma-digital',
            quantity=1,
            unit_price=Money(8, 'USD'),
            total_price=Money(8, 'USD'),
        )
        out = orders_get_tool.invoke({'order_number': order.order_number}).output
        self.assertEqual(out['items'][0]['product_id'], str(product.pk))


class OrdersSearchTotalTests(TestCase):
    """orders.search must report the real match total, not the page size — the
    same undercount bug catalog fixed for products.search."""

    def test_search_reports_real_total_not_page_size(self):
        from djmoney.money import Money

        from plugins.installed.orders.agent_tools import orders_search_tool
        from plugins.installed.orders.models import Order

        for i in range(3):
            Order.objects.create(
                email=f'c{i}@example.com',
                subtotal=Money(10, 'USD'),
                total=Money(10, 'USD'),
            )
        out = orders_search_tool.invoke({'limit': 2}).output
        self.assertEqual(out['total'], 3)
        self.assertEqual(out['returned'], 2)
        self.assertEqual(len(out['orders']), 2)
        self.assertNotIn('count', out)  # the misleading count=len(rows) key is gone

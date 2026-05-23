"""Tests for plugin contribution surfaces."""
from __future__ import annotations

from django.test import TestCase

from core.agents import agent_registry


class AgentCoreContributionsTests(TestCase):

    def test_worker_agent_is_registered(self):
        # Post-pivot (2026-05-23) — single generic Worker, not 5 specialists.
        names = {a.name for a in agent_registry.all_agents()}
        self.assertIn('worker', names)

    def test_worker_visible_to_every_audience(self):
        # Worker has audience='any' so it appears in storefront + merchant filters.
        for audience in ('storefront', 'merchant', 'system'):
            names = {a.name for a in agent_registry.agents_for_audience(audience)}
            self.assertIn('worker', names, f'worker missing from {audience} audience')

    def test_builtin_tools_registered(self):
        tool_names = {t.name for t in agent_registry.platform_tools()}
        for required in (
            'catalog.find_products',
            'catalog.get_product',
            'cart.summary',
            'orders.list_recent',
            'analytics.revenue_summary',
            'content.draft_product_description',
        ):
            self.assertIn(required, tool_names, f'missing built-in tool {required}')

    def test_inventory_tools_registered(self):
        names = {t.name for t in agent_registry.platform_tools()}
        self.assertIn('inventory.low_stock_report', names)
        self.assertIn('inventory.adjust_stock', names)

    def test_seo_tools_registered(self):
        names = {t.name for t in agent_registry.platform_tools()}
        self.assertIn('seo.get_meta', names)
        self.assertIn('seo.set_meta', names)

    def test_worker_sees_inventory_tools_via_scopes(self):
        agent = agent_registry.get_agent('worker')
        tool_names = {t.name for t in agent.get_tools()}
        # Worker has the full scope set so it can see every contributed tool.
        self.assertIn('inventory.low_stock_report', tool_names)
        self.assertIn('inventory.adjust_stock', tool_names)
        self.assertIn('seo.set_meta', tool_names)

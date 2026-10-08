"""The Developers hub (/dashboard/settings/developer/) is the ONE settings
entry for developer tooling: every DashboardPage(nav='settings',
section='developer') renders there as a tool card instead of a settings-
sidebar item, alongside the shell's own platform tools. Since v0.81.0 every
settings category works this way (docs/plans/dashboard-hubs-2026-10.md).
"""

# Lazy imports inside test methods are intentional (plugin load-order isolation).
# ruff: noqa: PLC0415
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase


class DevelopersHubTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username='staff', password='x', is_staff=True)
        self.client.force_login(user)

    def test_hub_lists_contributed_and_core_tools(self):
        resp = self.client.get('/dashboard/settings/developer/')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        # Contributed (agent_mcp + webhooks_ui DashboardPages)
        self.assertIn('API tokens', content)
        self.assertIn('/dashboard/apps/agent_mcp/tokens/', content)
        self.assertIn('Webhooks', content)
        # The shell's own tools, always reachable through the hub. With
        # release_notes on, its Version & updates page stands in for the
        # shell's updater card (one card, not two).
        for url in ('/dashboard/errors/', '/dashboard/settings/caching/'):
            self.assertIn(url, content)
        self.assertIn('/dashboard/apps/release_notes/version/', content)
        self.assertNotIn('href="/dashboard/updates/"', content)

    def test_developer_pages_are_not_individual_sidebar_entries(self):
        import re

        html = self.client.get('/dashboard/settings/developer/').content.decode()
        sidebar = re.search(r'<nav id="nav-settings".*?</nav>', html, re.S).group(0)
        # The settings sidebar lists categories only; the tools are cards.
        self.assertIn('/dashboard/settings/developer/', sidebar)
        for url in (
            '/dashboard/apps/agent_mcp/tokens/',
            '/dashboard/workflows/',
            '/dashboard/errors/',
        ):
            self.assertNotIn(url, sidebar)

    def test_disabled_plugin_card_vanishes(self):
        from plugins.registry import app_registry

        self.assertIn(
            '/dashboard/workflows/',
            self.client.get('/dashboard/settings/developer/').content.decode(),
        )
        self.addCleanup(app_registry.activate, 'workflows')
        app_registry.deactivate('workflows')
        resp = self.client.get('/dashboard/settings/developer/')
        self.assertNotIn('/dashboard/workflows/', resp.content.decode())

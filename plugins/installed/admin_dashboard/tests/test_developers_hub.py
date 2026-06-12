"""The Developers hub (/dashboard/settings/developer/) is the ONE settings
entry for developer tooling: every section='developer' DashboardPage renders
there as a card instead of an individual settings-sidebar item, alongside
the always-reachable core tools. IA redesign phase 2 —
docs/plans/dashboard-ia-redesign-2026-06.md.
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
        # Core tools, still reachable through the hub
        for url in ('/dashboard/tracking/', '/dashboard/errors/', '/dashboard/updates/'):
            self.assertIn(url, content)

    def test_developer_pages_are_not_individual_sidebar_entries(self):
        from django.test import RequestFactory

        from plugins.context_processors import plugin_context

        ctx = plugin_context(RequestFactory().get('/dashboard/settings/'))
        for section in ctx['settings_sections']:
            self.assertNotEqual(
                section['key'] if isinstance(section, dict) else section.key,
                'developer',
                'developer pages must render inside the hub, not the sidebar',
            )

    def test_disabled_plugin_card_vanishes(self):
        from plugins.registry import plugin_registry

        self.addCleanup(plugin_registry.activate, 'workflows')
        plugin_registry.deactivate('workflows')
        resp = self.client.get('/dashboard/settings/developer/')
        self.assertNotIn('/dashboard/apps/workflows/', resp.content.decode())

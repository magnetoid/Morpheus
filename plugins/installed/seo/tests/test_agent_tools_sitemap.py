"""seo.regenerate_sitemap agent tool — homed in the seo plugin (arch-debt refactor).

It was defined in core/assistant/tools/admin_ops.py but never surfaced in
get_default_tools() (dead in core). It is now a registry-contributed, disable-safe
seo tool. Deliberately NOT added to Linda's default catalog (_migrated_names) —
that preserves her prior catalog exactly; seo-scoped Workers reach it via the
registry.
"""

from __future__ import annotations

from django.test import TestCase


class SeoSitemapToolMigrationTests(TestCase):
    def test_plugin_contributes_the_tool(self):
        from plugins.registry import app_registry

        names = {t.name for t in app_registry.get('seo').contribute_agent_tools()}
        self.assertIn('seo.regenerate_sitemap', names)

    def test_registered_and_owned_by_seo(self):
        from morpheus.core import agent_registry

        self.assertIsNotNone(agent_registry.get_tool('seo.regenerate_sitemap'))
        self.assertEqual(agent_registry._tool_owners.get('seo.regenerate_sitemap'), 'seo')

    def test_not_in_lindas_default_catalog(self):
        # Behaviour-preserving: it was never in get_default_tools(), so it must
        # not appear now — only the registry (seo-scoped Workers) exposes it.
        from core.assistant.tools import get_default_tools

        names = {t.name for t in get_default_tools()}
        self.assertNotIn('seo.regenerate_sitemap', names)

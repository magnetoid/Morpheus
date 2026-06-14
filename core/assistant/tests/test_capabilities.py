"""platform.capabilities — Linda enumerates her full, plugin-aware toolset."""

from __future__ import annotations

from django.test import TestCase

from core.assistant.tools import get_default_tools
from core.assistant.tools.capabilities import capabilities_tool, plugins_describe_tool


class CapabilitiesToolTests(TestCase):
    def test_registered_in_default_tools(self):
        self.assertIn('platform.capabilities', {t.name for t in get_default_tools()})

    def test_enumerates_grouped_toolset(self):
        out = capabilities_tool.invoke({}).output
        self.assertGreater(out['total'], 20)
        self.assertGreater(out['domain_count'], 5)
        # Core platform-control domains Linda always has.
        self.assertIn('orders', out['domains'])
        self.assertIn('settings', out['domains'])
        self.assertIn('plugins', out['domains'])
        # Each entry carries a name + description.
        sample = out['domains']['orders'][0]
        self.assertIn('name', sample)
        self.assertIn('description', sample)

    def test_includes_plugin_contributed_tools(self):
        # Plugin tools (e.g. seo.*, crm.*, inventory.*) registered via
        # contribute_agent_tools() show up alongside core tools — proving the
        # capability surface is plugin-driven.
        out = capabilities_tool.invoke({}).output
        all_names = {t['name'] for tools in out['domains'].values() for t in tools}
        self.assertTrue(
            any(n.startswith(('seo.', 'crm.', 'inventory.', 'catalog.')) for n in all_names),
            'expected at least one plugin-contributed tool in the capability map',
        )


class PluginsDescribeToolTests(TestCase):
    def test_describes_active_plugin(self):
        # orders is a core commerce plugin with models + contributed tools.
        out = plugins_describe_tool.invoke({'name': 'orders'}).output
        self.assertEqual(out['name'], 'orders')
        self.assertIn('models', out)
        self.assertIsInstance(out['commands'], list)
        self.assertEqual(out['code_path'], 'plugins/installed/orders/')

    def test_unknown_plugin_lists_active(self):
        out = plugins_describe_tool.invoke({'name': 'does-not-exist'}).output
        self.assertIn('error', out)
        self.assertIn('active_plugins', out)
        self.assertIn('orders', out['active_plugins'])

    def test_registered_in_default_tools(self):
        self.assertIn('plugins.describe', {t.name for t in get_default_tools()})

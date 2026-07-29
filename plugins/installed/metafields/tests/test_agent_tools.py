"""metafields set/delete agent tools — migrated from core (arch-debt refactor).

Guards the move: names resolve for Linda, each registered once owned by
metafields, and the confirm / hard-gate guards still fire (they raise before any
model lookup, so no fixture is needed).
"""

from __future__ import annotations

from collections import Counter

from django.test import TestCase

from plugins.installed.metafields.agent_tools import metafields_delete_tool, metafields_set_tool

_MIGRATED = ('metafields.set', 'metafields.delete')


class MetafieldsAgentToolMigrationTests(TestCase):
    def test_plugin_contributes_the_tools(self):
        from plugins.registry import plugin_registry

        names = {t.name for t in plugin_registry.get('metafields').contribute_agent_tools()}
        self.assertTrue(set(_MIGRATED) <= names, f'missing: {set(_MIGRATED) - names}')

    def test_each_name_registered_once_and_owned_by_metafields(self):
        from morpheus.core import agent_registry

        for name in _MIGRATED:
            self.assertIsNotNone(agent_registry.get_tool(name), f'{name} not registered')
            self.assertEqual(agent_registry._tool_owners.get(name), 'metafields', f'{name} owner')

    def test_linda_catalog_sources_each_once(self):
        from core.assistant.tools import get_default_tools

        counts = Counter(t.name for t in get_default_tools())
        for name in _MIGRATED:
            self.assertEqual(counts[name], 1, f'{name} appears {counts[name]}x')

    def test_set_requires_confirmation(self):
        from morpheus.core import ToolError

        with self.assertRaises(ToolError):
            metafields_set_tool.invoke(
                {'model': 'catalog.Product', 'object_id': '1', 'key': 'k', 'value': 'v'}
            )

    def test_delete_is_hard_gated(self):
        from morpheus.core import ToolError

        with self.assertRaises(ToolError):  # no confirmation
            metafields_delete_tool.invoke(
                {'model': 'catalog.Product', 'object_id': '1', 'key': 'k'}
            )
        with self.assertRaises(ToolError):  # confirmed but no typed-back echo/ack
            metafields_delete_tool.invoke(
                {'model': 'catalog.Product', 'object_id': '1', 'key': 'k', 'confirmed': True}
            )

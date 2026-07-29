"""cms publish/unpublish agent tools — migrated from core (arch-debt refactor).

Guards the move is behavior-preserving: the names still resolve for Linda, each
is registered exactly once owned by cms, the confirm gate holds, and publish /
unpublish still flip page state.
"""

from __future__ import annotations

from collections import Counter

from django.test import TestCase

from plugins.installed.cms.agent_tools import cms_publish_page_tool, cms_unpublish_page_tool
from plugins.installed.cms.models import Page

_MIGRATED = ('cms.publish_page', 'cms.unpublish_page')


class CmsPublishToolMigrationTests(TestCase):
    def test_plugin_contributes_the_publish_tools(self):
        from plugins.registry import plugin_registry

        names = {t.name for t in plugin_registry.get('cms').contribute_agent_tools()}
        self.assertTrue(set(_MIGRATED) <= names, f'missing: {set(_MIGRATED) - names}')

    def test_each_name_registered_once_and_owned_by_cms(self):
        from morpheus.core import agent_registry

        for name in _MIGRATED:
            self.assertIsNotNone(agent_registry.get_tool(name), f'{name} not registered')
            self.assertEqual(agent_registry._tool_owners.get(name), 'cms', f'{name} owner')

    def test_linda_catalog_sources_each_once(self):
        from core.assistant.tools import get_default_tools

        counts = Counter(t.name for t in get_default_tools())
        for name in _MIGRATED:
            self.assertEqual(counts[name], 1, f'{name} appears {counts[name]}x')

    def test_publish_requires_confirmation(self):
        from morpheus.core import ToolError

        with self.assertRaises(ToolError):
            cms_publish_page_tool.invoke({'slug': 'x'})

    def test_publish_and_unpublish_flip_state(self):
        Page.objects.create(slug='hello', title='Hello', body='hi there', state='draft')
        cms_publish_page_tool.invoke({'slug': 'hello', 'confirmed': True})
        self.assertEqual(Page.objects.get(slug='hello').state, 'published')
        cms_unpublish_page_tool.invoke({'slug': 'hello', 'confirmed': True})
        self.assertEqual(Page.objects.get(slug='hello').state, 'draft')

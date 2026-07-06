"""i18n product-translation agent tools — migrated core/i18n -> catalog.

i18n.translate_product / i18n.list_translations query catalog.Product, so they
now live in the catalog plugin (contributed + registered there) instead of being
registered by core/i18n/apps.py. They were registry-only (never in Linda's
_migrated_names), so that stays true — behaviour-preserving. The generic i18n
tools (i18n.languages / get_translations / set_translation) remain in core.
"""

from __future__ import annotations

from django.test import TestCase

_MIGRATED = ('i18n.translate_product', 'i18n.list_translations')


class I18nProductToolMigrationTests(TestCase):
    def test_catalog_contributes_the_tools(self):
        from plugins.registry import plugin_registry

        names = {t.name for t in plugin_registry.get('catalog').contribute_agent_tools()}
        self.assertTrue(set(_MIGRATED) <= names, f'missing: {set(_MIGRATED) - names}')

    def test_each_name_registered_once_and_owned_by_catalog(self):
        from core.agents import agent_registry

        for name in _MIGRATED:
            self.assertIsNotNone(agent_registry.get_tool(name), f'{name} not registered')
            self.assertEqual(agent_registry._tool_owners.get(name), 'catalog', f'{name} owner')

    def test_generic_i18n_tools_stay_core(self):
        # The any-object translation tools remain registered by core.i18n.
        from core.agents import agent_registry

        for name in ('i18n.languages', 'i18n.get_translations', 'i18n.set_translation'):
            tool = agent_registry.get_tool(name)
            if tool is not None:  # registered under core.i18n, not catalog
                self.assertEqual(agent_registry._tool_owners.get(name), 'core.i18n')

    def test_not_in_lindas_default_catalog(self):
        from core.assistant.tools import get_default_tools

        names = {t.name for t in get_default_tools()}
        for name in _MIGRATED:
            self.assertNotIn(name, names)

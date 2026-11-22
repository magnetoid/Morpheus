"""Linda reads and changes the active theme's settings (v0.185.0).

`theme.describe` reads them; `theme.set` changes one, only after the merchant's
own yes (requires_approval), checked against the setting's type the way
`settings.set` checks an app's.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from core.assistant.tools.filesystem import ToolError
from themes.models import ThemeConfig
from themes.registry import theme_registry

# The active theme in tests (dot_books) declares no settings, so each test gives it one.
SCHEMA = {
    'type': 'object',
    'properties': {
        'tagline': {'type': 'string', 'default': 'A quiet shelf', 'title': 'Tagline'},
    },
}


class ThemeToolsTests(TestCase):
    def setUp(self):
        self.theme = theme_registry.active
        self.theme.invalidate_config_cache()
        self.addCleanup(self.theme.invalidate_config_cache)
        schema = patch.object(type(self.theme), 'get_config_schema', return_value=SCHEMA)
        schema.start()
        self.addCleanup(schema.stop)

    def _set(self, **args):
        from core.assistant.tools.admin_ops import theme_set_tool

        return theme_set_tool.invoke(args)

    def _schema_with(self, **extra):
        props = {**self.theme.get_config_schema().get('properties', {}), **extra}
        return patch.object(
            type(self.theme),
            'get_config_schema',
            return_value={'type': 'object', 'properties': props},
        )

    def test_describe_lists_the_active_themes_settings(self):
        from core.assistant.tools.admin_ops import theme_describe_tool

        out = theme_describe_tool.invoke({}).output
        self.assertEqual(out['theme'], self.theme.name)
        self.assertEqual(out['label'], self.theme.label)
        entries = {e['key']: e for e in out['settings']}
        self.assertEqual(entries['tagline']['default'], 'A quiet shelf')
        self.assertIs(entries['tagline']['agent_writable'], True)

    def test_set_needs_the_merchants_yes(self):
        with self.assertRaises(ToolError):
            self._set(key='tagline', value='Hi')
        self.assertFalse(ThemeConfig.objects.filter(theme_name=self.theme.name).exists())

    def test_set_changes_the_setting(self):
        self._set(key='tagline', value='Hi', confirmed=True)
        self.assertEqual(self.theme.get_config_value('tagline'), 'Hi')

    def test_set_refuses_an_unknown_key(self):
        with self.assertRaises(ToolError) as ctx:
            self._set(key='no_such_setting', value='x', confirmed=True)
        self.assertTrue(str(ctx.exception).endswith('Nothing was changed.'), str(ctx.exception))
        self.assertFalse(ThemeConfig.objects.filter(theme_name=self.theme.name).exists())

    def test_set_refuses_a_value_of_the_wrong_type(self):
        with (
            self._schema_with(columns={'type': 'integer', 'default': 3}),
            self.assertRaises(ToolError) as ctx,
        ):
            self._set(key='columns', value='abc', confirmed=True)
        self.assertTrue(str(ctx.exception).endswith('Nothing was changed.'), str(ctx.exception))
        self.assertFalse(ThemeConfig.objects.filter(theme_name=self.theme.name).exists())

    def test_set_refuses_a_key_only_the_merchant_may_change(self):
        prop = {'type': 'string', 'default': '', 'x-agent-writable': False}
        with self._schema_with(owner_only=prop), self.assertRaises(ToolError) as ctx:
            self._set(key='owner_only', value='x', confirmed=True)
        self.assertTrue(str(ctx.exception).endswith('Nothing was changed.'), str(ctx.exception))
        self.assertFalse(ThemeConfig.objects.filter(theme_name=self.theme.name).exists())

    def test_set_needs_approval_and_both_are_lindas(self):
        from core.assistant.tools import get_default_tools
        from core.assistant.tools.admin_ops import theme_describe_tool, theme_set_tool

        self.assertIs(theme_set_tool.requires_approval, True)
        self.assertEqual(theme_set_tool.scopes, ['system.write'])
        self.assertEqual(theme_describe_tool.scopes, ['system.read'])
        names = [t.name for t in get_default_tools()]
        self.assertIn('theme.describe', names)
        self.assertIn('theme.set', names)


class ThemeToolsInTheSkillTests(TestCase):
    """The store skill sends a theme's settings to the theme tools: `settings.set` on
    the storefront app stores an undeclared key "as given", so a theme setting
    changed that way reports success and changes nothing."""

    def test_the_store_skill_names_the_theme_tools(self):
        from pathlib import Path

        from django.conf import settings

        skill = Path(settings.BASE_DIR) / (
            'core/assistant/janus_skills/ecommerce/morpheus-store-operator/SKILL.md'
        )
        text = skill.read_text(encoding='utf-8')
        self.assertIn('`theme.describe`', text)
        self.assertIn('`theme.set`', text)

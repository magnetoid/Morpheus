"""Linda reads the same help: help.apps and help.read, for every staff role in
every mode, never for a shopper's agent."""

from __future__ import annotations

import re
import types

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.agents.base import MorpheusAgent
from core.assistant.modes import MODES
from core.assistant.prompts import build_system_prompt
from plugins.installed.agent_mcp.linda_turn import LindaTurn, catalogue
from plugins.installed.release_notes.help_tools import help_apps_tool, help_read_tool
from plugins.registry import app_registry

CONV = 'user:help-tools-test'


def _names(user, mode: str) -> set[str]:
    return {t.name for t in catalogue(LindaTurn(user=user, conversation_key=CONV, mode_slug=mode))}


class HelpToolTests(TestCase):
    def test_help_apps_lists_every_installed_app(self):
        apps = {a['name']: a for a in help_apps_tool.handler().output['apps']}
        self.assertEqual(set(apps), {p.name for p in app_registry.all_plugins()})
        self.assertTrue(apps['reviews']['on'])
        self.assertEqual(apps['reviews']['area'], 'Products')

    def test_help_read_turns_markers_into_names_and_paths(self):
        text = help_read_tool.handler(app='release_notes').output['text']
        self.assertIn('Version & updates (/dashboard/apps/release_notes/version/)', text)
        self.assertNotRegex(text, r'\((page|settings|field|section|app):')

    def test_help_read_says_where_things_are_and_what_linda_can_do(self):
        text = help_read_tool.handler(app='reviews').output['text']
        self.assertIn('- Products › Reviews (/dashboard/reviews/)', text)
        self.assertIn('reviews.approve (asks first)', text)

    def test_an_unknown_app_gets_the_closest_names(self):
        out = help_read_tool.handler(app='reviewz').output
        self.assertIn('error', out)
        self.assertIn('reviews', out['closest'])

    def test_every_staff_member_has_help_in_every_mode(self):
        plugin = app_registry.get('rbac')
        plugin.set_config('enforcement_mode', 'enforce')
        plugin.invalidate_config_cache()
        self.addCleanup(plugin.invalidate_config_cache)
        nobody = get_user_model().objects.create_user(
            username='help-norole', email='nr@example.test', password='pw', is_staff=True
        )
        for mode in MODES:
            with self.subTest(mode=mode.slug):
                names = _names(nobody, mode.slug)
                self.assertIn('help.apps', names)
                self.assertIn('help.read', names)

    def test_lindas_instructions_name_only_help_tools_she_has(self):
        prompt = build_system_prompt()
        self.assertIn('`help.read`', prompt)
        staff = types.SimpleNamespace(is_staff=True, is_superuser=False, pk=1)
        names = _names(staff, 'general')
        for name in re.findall(r'`(help\.[a-z_]+)`', prompt):
            self.assertIn(name, names)


class StorefrontAgentTests(TestCase):
    def test_a_storefront_agent_never_gets_a_scope_less_tool(self):
        class Shop(MorpheusAgent):
            name = 'help_test_shop'
            label = 'Shop'
            audience = 'storefront'
            scopes = ['catalog.read']

        names = {t.name for t in Shop().get_tools()}
        self.assertNotIn('help.apps', names)
        self.assertNotIn('help.read', names)

    def test_a_staff_agent_gets_the_help_tools(self):
        class Staff(MorpheusAgent):
            name = 'help_test_staff'
            label = 'Staff'
            audience = 'merchant'
            scopes = ['catalog.read']

        self.assertIn('help.read', {t.name for t in Staff().get_tools()})

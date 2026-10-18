"""With release_notes off, every help surface is gone (CLAUDE.md's second litmus
test): the Help area, every Help link, the menu entries, Linda's tools and her
help line."""

from __future__ import annotations

import types

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.assistant.prompts import build_system_prompt
from plugins.installed.agent_mcp.linda_turn import LindaTurn, catalogue
from plugins.registry import app_registry


class HelpDisableTests(TestCase):
    def setUp(self):
        boss = get_user_model().objects.create_user(
            username='help-off',
            email='ho@example.test',
            password='pw',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(boss)
        app_registry.deactivate('release_notes')
        self.addCleanup(app_registry.activate, 'release_notes')

    def test_the_help_area_is_gone(self):
        for url in ('/dashboard/help/', '/dashboard/help/reviews/', '/dashboard/apps/release_notes/help/'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_no_help_link_renders_anywhere(self):
        for url in ('/dashboard/', '/dashboard/reviews/', '/dashboard/orders/', '/dashboard/apps/'):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertNotIn('class="page-help"', html)
                self.assertNotIn('href="/dashboard/help/', html)

    def test_linda_loses_the_tools_and_the_line(self):
        staff = types.SimpleNamespace(is_staff=True, is_superuser=False, pk=1)
        names = {
            t.name
            for t in catalogue(LindaTurn(user=staff, conversation_key='user:help-off', mode_slug='general'))
        }
        self.assertNotIn('help.apps', names)
        self.assertNotIn('help.read', names)
        self.assertNotIn('help.read', build_system_prompt())

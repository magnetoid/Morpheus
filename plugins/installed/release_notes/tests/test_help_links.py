"""Help is linked from the screens: every dashboard page, the user menu, the Apps
catalogue. The shell asks (DASHBOARD_PAGE_HELP, DASHBOARD_USER_MENU) and the help
app answers, so base.html links no app page itself."""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils.html import escape

from plugins import app_help
from plugins.installed.admin_dashboard import navigation

_LINK = re.compile(r'<p class="page-help"><a href="([^"]+)"')


class PageHelpLinkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.boss = get_user_model().objects.create_user(
            username='help-links',
            email='hl@example.test',
            password='pw',
            is_staff=True,
            is_superuser=True,
        )

    def setUp(self):
        self.client.force_login(self.boss)

    def _help_link(self, url: str) -> str | None:
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, url)
        m = _LINK.search(resp.content.decode())
        return m.group(1) if m else None

    def test_an_apps_own_page_links_its_help(self):
        self.assertEqual(self._help_link('/dashboard/reviews/'), '/dashboard/help/reviews/')

    def test_a_settings_tool_links_its_apps_help(self):
        self.assertEqual(
            self._help_link('/dashboard/apps/feedback/tickets/'), '/dashboard/help/feedback/'
        )

    def test_an_apps_settings_form_links_its_help(self):
        self.assertEqual(
            self._help_link('/dashboard/settings/newsletter/'), '/dashboard/help/newsletter/'
        )

    def test_a_shell_tab_links_the_app_it_belongs_to(self):
        self.assertEqual(self._help_link('/dashboard/orders/'), '/dashboard/help/orders/')
        self.assertEqual(self._help_link('/dashboard/products/'), '/dashboard/help/catalog/')

    def test_a_page_of_no_app_links_the_help_index(self):
        self.assertEqual(self._help_link('/dashboard/'), '/dashboard/help/')

    def test_the_help_pages_carry_no_help_link(self):
        self.assertIsNone(self._help_link('/dashboard/help/'))
        self.assertIsNone(self._help_link('/dashboard/help/reviews/'))

    def test_every_shell_tab_names_an_app_with_a_folder(self):
        apps = set(app_help.tree_apps())
        for tab in navigation.CORE_TABS:
            with self.subTest(tab=tab.label):
                self.assertIn(tab.app, apps)


class MenuAndCatalogueTests(TestCase):
    def setUp(self):
        boss = get_user_model().objects.create_user(
            username='help-menu',
            email='hm@example.test',
            password='pw',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(boss)

    def test_the_user_menu_comes_from_the_help_app(self):
        html = self.client.get('/dashboard/').content.decode()
        self.assertIn('href="/dashboard/help/"', html)
        self.assertIn('href="/dashboard/apps/release_notes/about/"', html)
        # The version pill rides on the contributed entry (the top bar shows the
        # version too, so look for it inside the Version link itself).
        self.assertRegex(
            html,
            r'href="/dashboard/apps/release_notes/version/"[^>]*>.*?Version &amp; updates '
            r'<span class="pill pill-info"[^>]*>' + re.escape(settings.MORPHEUS_VERSION),
        )

    def test_the_shell_names_no_app_page(self):
        base = (
            Path(settings.BASE_DIR)
            / 'plugins/installed/admin_dashboard/templates/admin_dashboard/base.html'
        )
        self.assertNotIn('release_notes', base.read_text(encoding='utf-8'))

    def test_the_catalogue_shows_each_apps_summary_and_help(self):
        html = self.client.get('/dashboard/apps/').content.decode()
        start = html.index('data-app="release_notes"')
        end = html.find('data-app=', start + 10)
        card = html[start : end if end != -1 else None]
        self.assertIn(escape(app_help.summary('release_notes')), card)
        self.assertIn('href="/dashboard/help/release_notes/"', card)

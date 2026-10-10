"""The account icon opens a menu, and partners find their way in from it.

Owner's asks (2026-10-10): a dropdown on the account icon, and visible links to
the affiliate and vendor dashboards, or their sign-in, on Supernatural Shop and
Irving Survival. Both dashboards send a visitor to sign in and back, so one link
per role serves both. The menu names links, never the shopper: a signed-in page
carries no Cache-Control, and an edge cache may still keep it.
"""

from __future__ import annotations

import re

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from plugins.registry import app_registry
from themes.registry import theme_registry

THEMES = ('supernatural_shop', 'irving_survival')


class AccountMenuTests(TestCase):
    def _activate(self, theme: str) -> None:
        override = override_settings(MORPHEUS_ACTIVE_THEME=theme)
        override.enable()
        self.addCleanup(override.disable)
        previous = theme_registry._active_name
        theme_registry.set_active(theme)
        self.addCleanup(setattr, theme_registry, '_active_name', previous)
        cache.clear()
        self.addCleanup(cache.clear)

    def _page(self, client: Client | None = None) -> str:
        response = (client or self.client).get('/no-such-page-account-menu-probe/')
        self.assertEqual(response.status_code, 404)
        return response.content.decode()

    @staticmethod
    def _items(body: str) -> dict[str, str]:
        """``data-acct-item`` → href, for every link in the account menu."""
        return dict(
            (item, href)
            for href, item in re.findall(r'<a href="([^"]+)"[^>]*data-acct-item="([^"]+)"', body)
        )

    def test_a_visitor_gets_sign_in_and_the_partner_logins(self):
        for theme in THEMES:
            with self.subTest(theme=theme):
                self._activate(theme)
                body = self._page()
                self.assertIn('data-acct-toggle', body)
                self.assertIn('aria-controls="acct-menu"', body)
                items = self._items(body)
                self.assertEqual(items.get('sign-in'), '/auth/login/')
                self.assertEqual(items.get('sign-up'), '/auth/signup/')
                self.assertEqual(items.get('affiliate'), '/affiliates/me/')
                self.assertEqual(items.get('vendor'), '/vendor/me/')
                self.assertNotIn('sign-out', items)

    def test_a_signed_in_shopper_gets_the_account_and_sign_out_but_no_name(self):
        shopper = get_user_model().objects.create_user(
            username='menu-shopper', email='menu.shopper@example.com', password='x'
        )
        client = Client()
        client.force_login(shopper)
        for theme in THEMES:
            with self.subTest(theme=theme):
                self._activate(theme)
                body = self._page(client)
                items = self._items(body)
                self.assertEqual(items.get('account'), '/account/')
                self.assertEqual(items.get('orders'), '/account/orders/')
                self.assertEqual(items.get('sign-out'), '/auth/logout/')
                self.assertEqual(items.get('affiliate'), '/affiliates/me/')
                self.assertEqual(items.get('vendor'), '/vendor/me/')
                self.assertNotIn('sign-in', items)
                self.assertNotIn('menu.shopper@example.com', body)

    def test_the_footer_names_both_partner_doors(self):
        for theme in THEMES:
            with self.subTest(theme=theme):
                self._activate(theme)
                body = self._page()
                self.assertRegex(body, r'href="/affiliates/me/"[^>]*data-partner-link="affiliate"')
                self.assertRegex(body, r'href="/vendor/me/"[^>]*data-partner-link="vendor"')

    def test_a_switched_off_app_takes_its_links_with_it(self):
        for app, path in (('affiliates', '/affiliates/me/'), ('marketplace', '/vendor/me/')):
            for theme in THEMES:
                with self.subTest(app=app, theme=theme):
                    self._activate(theme)
                    self.assertTrue(app_registry.is_active(app))
                    app_registry.deactivate(app)
                    try:
                        cache.clear()
                        body = self._page()
                    finally:
                        app_registry.activate(app)
                        cache.clear()
                    self.assertNotIn(f'href="{path}"', body)
                    self.assertIn('data-acct-toggle', body)  # the menu itself stays

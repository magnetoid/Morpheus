"""Irving puts vendors and affiliates in its menus (owner's ask, 2026-10-10).

The header, the mobile menu and the footer link the supplier marketplace and
the affiliate program — each only while its app is on, because a link to a
disabled app's page is a 404 the theme would keep serving.
"""

from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase

from plugins.registry import app_registry
from themes.test_head_contract import _activate_theme

_SUPPLIERS = '<a href="/marketplace/">Suppliers</a>'
_AFFILIATES = '<a href="/affiliates/">Affiliates</a>'
_PROGRAM = '<a href="/affiliates/">Affiliate program</a>'


class IrvingMenuTests(TestCase):
    def setUp(self):
        _activate_theme(self, 'irving_survival')

    def _home(self) -> str:
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def test_header_mobile_and_footer_link_suppliers_and_affiliates(self):
        html = self._home()
        # Once in the header, once in the mobile menu.
        self.assertEqual(html.count(_SUPPLIERS), 2)
        self.assertEqual(html.count(_AFFILIATES), 2)
        self.assertIn('Work with us', html)
        self.assertIn('<a href="/vendors/">Our suppliers</a>', html)
        self.assertIn('<a href="/marketplace/">Sell with us</a>', html)
        self.assertIn(_PROGRAM, html)

    def test_a_disabled_app_leaves_no_link_behind(self):
        for name, links in (
            ('affiliates', (_AFFILIATES, _PROGRAM)),
            ('marketplace', (_SUPPLIERS, '<a href="/vendors/">Our suppliers</a>')),
        ):
            with self.subTest(app=name):
                self.assertTrue(app_registry.is_active(name))
                app_registry.deactivate(name)
                cache.clear()
                try:
                    html = self._home()
                    for link in links:
                        self.assertNotIn(link, html)
                finally:
                    app_registry.activate(name)
                    cache.clear()

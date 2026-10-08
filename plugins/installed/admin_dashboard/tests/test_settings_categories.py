"""Settings categories since v0.81.0 (docs/plans/dashboard-hubs-2026-10.md):
eleven categories plus "Other apps" for an out-of-tree app that names none;
apps' settings pages are tool cards on their category, old slugs redirect,
caching is a Developer card with its URL kept alive, product-type panels sit
in General.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase


class SettingsCategoriesTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username='staff', password='x', is_staff=True)
        self.client.force_login(user)

    def test_category_list_is_consolidated(self):
        from plugins.installed.admin_dashboard.settings_categories import SETTINGS_CATEGORIES

        slugs = [c.slug for c in SETTINGS_CATEGORIES]
        # General leads (after the Settings overview link); commerce config follows.
        self.assertEqual(
            slugs,
            [
                'general',
                'payments',
                'shipping',
                'storefront',
                'channels',
                'marketing',
                'ai',
                'notifications',
                'team',
                'developer',
                'data',
                'apps',
            ],
        )

    def test_every_in_tree_app_picks_a_category(self):
        # "Other apps" exists for out-of-tree apps; nothing shipped lands there.
        from plugins.installed.admin_dashboard import navigation
        from plugins.registry import app_registry

        stray = [
            e['plugin']
            for e in app_registry.all_settings_panels()
            if navigation.settings_category_key(e['panel'].category) == 'apps'
        ]
        stray += [t.label for t in navigation.tools() if t.category == 'apps']
        self.assertEqual(stray, [])

    def test_old_category_slugs_redirect(self):
        resp = self.client.get('/dashboard/settings/taxes/')
        self.assertRedirects(resp, '/dashboard/settings/shipping/', fetch_redirect_response=False)

    def test_settings_pages_are_tool_cards_on_their_category(self):
        html = self.client.get('/dashboard/settings/shipping/').content.decode()
        for url in ('/dashboard/shipping/zones/', '/dashboard/tax/regions/'):
            self.assertIn(url, html)

    def test_caching_url_survives_category_removal(self):
        # Dispatched before the category lookup, linked from the hub.
        resp = self.client.get('/dashboard/settings/caching/')
        self.assertEqual(resp.status_code, 200)

    def test_product_type_panels_render_on_general(self):
        resp = self.client.get('/dashboard/settings/general/')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('/dashboard/settings/audiobooks/', content)
        # book_product's panel held only controls nothing read (default paper and
        # print type, the 3D preview switch); v0.76.4 removed them and the panel
        # with them, so a page with no controls is not offered.
        self.assertNotIn('/dashboard/settings/book_product/', content)

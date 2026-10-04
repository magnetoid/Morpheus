"""Settings IA after redesign phase 3: 10 declared categories (8 visible —
shipping/taxes are page-owned and suppressed from the sidebar), caching
demoted to a Developers-hub card with its URL kept alive, product-type
panels merged into General. docs/plans/dashboard-ia-redesign-2026-06.md.
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
                'taxes',
                'channels',
                'ai',
                'marketing',
                'notifications',
                'developer',
                'apps',
            ],
        )

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

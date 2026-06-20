"""Morpheus Brain page — renders, staff-gated, and degrades gracefully."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.installed.morpheus_brain.views import (
    _code_tab,
    _content_tab,
    _improvements_tab,
    _plugins_tab,
    _storefront_tab,
)


class TabHelpersTests(TestCase):
    def test_helpers_never_raise(self):
        # Empty DB / some engines absent → each helper returns a dict, no error.
        for fn in (_plugins_tab, _code_tab, _content_tab, _storefront_tab, _improvements_tab):
            out = fn()
            self.assertIsInstance(out, dict)
            self.assertIn('available', out)

    def test_plugins_tab_lists_registry(self):
        out = _plugins_tab()
        self.assertTrue(out['available'])
        # The registry has many plugins active in tests.
        self.assertGreater(out['total'], 0)
        self.assertGreater(out['active_count'], 0)


class BrainPageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(
            username='boss', email='b@x.io', password='pw', is_staff=True
        )

    def test_renders_for_staff(self):
        self.client.force_login(self.staff)
        resp = self.client.get('/dashboard/apps/morpheus_brain/brain/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Morpheus Brain')
        self.assertContains(resp, 'Plugins')

    def test_anon_blocked(self):
        resp = self.client.get('/dashboard/apps/morpheus_brain/brain/')
        self.assertIn(resp.status_code, (301, 302, 403))

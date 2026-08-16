"""Central updating UI — the dashboard Apply action wraps core.updates safely."""

# ruff: noqa: PLC0415
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class UpdatesApplyTests(TestCase):
    def setUp(self):
        u = get_user_model().objects.create_user(
            username='upd', email='u@example.test', password='pw', is_staff=True
        )
        self.client.force_login(u)
        self.url = reverse('admin_dashboard:updates_apply')

    def test_get_does_not_apply(self):
        with patch('core.updates.apply_platform_update') as ap:
            r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        ap.assert_not_called()

    def test_post_calls_guarded_updater(self):
        with patch(
            'core.updates.apply_platform_update',
            return_value={'status': 'applied', 'from': 'abc1234', 'to': 'v1.2'},
        ) as ap:
            r = self.client.post(self.url)
        self.assertEqual(r.status_code, 302)
        ap.assert_called_once_with(confirm=True)

    def test_disabled_is_reported_not_fatal(self):
        with patch(
            'core.updates.apply_platform_update',
            return_value={'status': 'disabled', 'reason': 'off'},
        ):
            r = self.client.post(self.url)
        self.assertEqual(r.status_code, 302)

    def test_page_renders(self):
        r = self.client.get(reverse('admin_dashboard:updates'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Updates')


class ComponentUpdatesSurfaceTests(TestCase):
    """The per-app / per-theme channel on the Updates page."""

    COMPONENT = {
        'kind': 'theme',
        'name': 'aurora_theme',
        'current': '1.0.0',
        'latest': '1.1.0',
        'artifact': 'https://x/t.tgz',
        'sha256': 'ab' * 32,
        'min_core': '',
        'notes': '',
        'core_ok': True,
    }

    def setUp(self):
        from django.core.cache import cache

        cache.delete('morpheus:update_status')
        u = get_user_model().objects.create_user(
            username='cu', email='c@example.test', password='pw', is_staff=True
        )
        self.client.force_login(u)
        self.page = reverse('admin_dashboard:updates')
        self.apply = reverse('admin_dashboard:updates_apply_component')

    def _cache(self, components):
        from django.core.cache import cache

        cache.set(
            'morpheus:update_status',
            {'source': 'git', 'available': 'no', 'components': components},
            300,
        )

    def test_page_lists_cached_component_updates_with_an_apply_button(self):
        self._cache([self.COMPONENT])
        r = self.client.get(self.page)
        self.assertContains(r, 'aurora_theme')
        self.assertContains(r, '1.1.0')
        self.assertContains(r, self.apply)

    def test_core_blocked_component_shows_no_apply_button(self):
        self._cache([{**self.COMPONENT, 'core_ok': False, 'min_core': 'v9.0.0'}])
        r = self.client.get(self.page)
        self.assertContains(r, 'needs core v9.0.0 first')
        self.assertNotContains(r, f'action="{self.apply}"')

    def test_page_without_component_updates_says_so(self):
        r = self.client.get(self.page)
        self.assertContains(r, 'Nothing newer is published')

    def test_get_apply_does_not_apply(self):
        with patch('core.component_updates.apply_component_update') as ap:
            r = self.client.get(self.apply)
        self.assertEqual(r.status_code, 302)
        ap.assert_not_called()

    def test_post_apply_calls_the_guarded_engine_with_confirm(self):
        with patch(
            'core.component_updates.apply_component_update',
            return_value={'status': 'applied', 'from': '1.0.0', 'to': '1.1.0'},
        ) as ap:
            r = self.client.post(self.apply, {'kind': 'theme', 'name': 'aurora_theme'})
        self.assertEqual(r.status_code, 302)
        ap.assert_called_once_with('theme', 'aurora_theme', confirm=True)

    def test_check_refreshes_the_cache_so_components_appear(self):
        """The Check button must populate the same cache the page reads —
        otherwise a merchant clicks Check and still sees nothing."""
        status = {'source': 'git', 'available': 'no', 'components': [self.COMPONENT]}
        with patch('core.updates.platform_update_status', return_value=dict(status)):
            self.client.post(reverse('admin_dashboard:updates_check'))
        from core.updates import cached_update_status

        self.assertEqual(cached_update_status()['components'], [self.COMPONENT])

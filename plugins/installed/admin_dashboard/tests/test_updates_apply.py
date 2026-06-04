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

"""The bootstrap page answers at its own address, and its "Try again" link
leads back to it (it pointed at /dashboard/start/, a 404, until v0.149.1)."""

from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class StartPageTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='owner', email='owner@example.com', password='x', is_staff=True
        )
        self.client.force_login(self.staff)
        self.url = reverse('store_bootstrap:start')

    def test_the_page_lives_under_the_apps_prefix(self):
        self.assertEqual(self.url, '/dashboard/apps/store_bootstrap/start/')
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_a_failed_run_links_back_to_the_page(self):
        with mock.patch(
            'plugins.installed.store_bootstrap.services.bootstrap_store_from_prompt',
            return_value={'error': 'No AI provider is set up.'},
        ):
            response = self.client.post(self.url, {'prompt': 'A small tea shop.'})
        self.assertContains(response, 'No AI provider is set up.')
        self.assertContains(response, f'href="{self.url}"')
        self.assertNotContains(response, 'href="/dashboard/start/"')

    def test_anonymous_visitors_are_sent_to_sign_in(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

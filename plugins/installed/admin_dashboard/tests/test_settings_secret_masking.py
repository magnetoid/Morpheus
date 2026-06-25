"""Write-only secrets in the shared settings-panel renderer.

A JSON-schema ``format: 'password'`` field (e.g. staff_sso's
``oidc_client_secret``, audiobooks' ElevenLabs key) must NEVER be echoed back
into the rendered settings page (credential-disclosure guard), and a blank
submit must PRESERVE the stored secret rather than wipe it.

We drive the real shared renderer + the real shared POST save handler through
``staff_sso``'s panel (it owns a ``format: password`` field and lives under the
Developers category).
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.registry import plugin_registry

SECRET = 'super-secret-oidc-value-9f3a'


class SecretMaskingTests(TestCase):
    PLUGIN = 'staff_sso'

    def setUp(self):
        user = get_user_model().objects.create_user(username='staff', password='x', is_staff=True)
        self.client.force_login(user)
        # Activate staff_sso so its SettingsPanel (with the format:password
        # field) is collected and rendered by the shared renderer.
        plugin_registry.activate(self.PLUGIN)
        self.plugin = plugin_registry.get(self.PLUGIN)
        # Persist a saved secret to prove it is masked on render / preserved on
        # a blank submit.
        self.plugin.set_config('oidc_client_secret', SECRET)

    def tearDown(self):
        plugin_registry.deactivate(self.PLUGIN)

    def test_saved_secret_is_not_rendered_in_page_source(self):
        resp = self.client.get('/dashboard/settings/developer/')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        # The secret value must not appear anywhere in the page source.
        self.assertNotIn(SECRET, html)
        # The field renders as a write-only password input with a placeholder.
        self.assertIn('name="oidc_client_secret"', html)
        self.assertIn('type="password"', html)
        self.assertIn('(unchanged)', html)

    def test_blank_submit_preserves_stored_secret(self):
        # POST the panel with the password field left blank — the canonical
        # "I didn't touch the secret" submit.
        resp = self.client.post(
            f'/dashboard/settings/{self.PLUGIN}/',
            data={
                'oidc_issuer': 'https://acme.example/.well-known/openid-configuration',
                'oidc_client_id': 'cid',
                'oidc_client_secret': '',  # blank → must NOT wipe the stored secret
                'oidc_scopes': 'openid email profile',
                'allowed_domains': 'acme.com',
                'staff_groups': '',
            },
        )
        self.assertIn(resp.status_code, (200, 302))
        self.plugin.invalidate_config_cache()
        self.assertEqual(self.plugin.get_config_value('oidc_client_secret'), SECRET)

    def test_non_blank_submit_updates_secret(self):
        # Sanity: a real, non-empty value still overwrites the stored secret.
        resp = self.client.post(
            f'/dashboard/settings/{self.PLUGIN}/',
            data={
                'oidc_issuer': 'https://acme.example/.well-known/openid-configuration',
                'oidc_client_id': 'cid',
                'oidc_client_secret': 'a-new-secret',
                'oidc_scopes': 'openid email profile',
                'allowed_domains': 'acme.com',
                'staff_groups': '',
            },
        )
        self.assertIn(resp.status_code, (200, 302))
        self.plugin.invalidate_config_cache()
        self.assertEqual(self.plugin.get_config_value('oidc_client_secret'), 'a-new-secret')

"""PWA plugin smoke tests — the three public endpoints + their
content-type contracts (browsers are strict about these for
installability)."""

# ruff: noqa: PLC0415
from __future__ import annotations

import json

from django.test import Client, TestCase


class PwaEndpointTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_manifest_served_with_manifest_content_type(self):
        resp = self.client.get('/manifest.webmanifest')
        self.assertEqual(resp.status_code, 200)
        # Must be the manifest content type for Chrome to treat the
        # site as installable.
        self.assertEqual(resp['Content-Type'], 'application/manifest+json')
        data = json.loads(resp.content)
        # Required keys for an installable PWA.
        for key in ('name', 'short_name', 'start_url', 'display', 'icons'):
            self.assertIn(key, data)
        self.assertEqual(data['display'], 'standalone')
        # At least one 192 + one 512 icon, and a maskable.
        sizes = {i['sizes'] for i in data['icons']}
        self.assertIn('192x192', sizes)
        self.assertIn('512x512', sizes)
        purposes = {i.get('purpose') for i in data['icons']}
        self.assertIn('maskable', purposes)

    def test_service_worker_js_content_type_and_scope_header(self):
        resp = self.client.get('/sw.js')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp['Content-Type'].startswith('application/javascript'))
        # Root scope must be allowed even though the file isn't at /.
        self.assertEqual(resp['Service-Worker-Allowed'], '/')
        body = resp.content.decode()
        # Core SW lifecycle hooks present.
        self.assertIn("addEventListener('install'", body)
        self.assertIn("addEventListener('fetch'", body)
        # Auth/cart/checkout must be excluded from caching.
        self.assertIn('auth|cart|checkout', body)

    def test_offline_page_renders(self):
        resp = self.client.get('/offline/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'offline', resp.content.lower())

    def test_sw_offline_url_toggles_with_config(self):
        """When offline_enabled is False, the SW body shouldn't precache
        an offline URL."""
        from plugins.models import PluginConfig

        PluginConfig.objects.update_or_create(
            plugin_name='pwa',
            defaults={'is_enabled': True, 'config': {'offline_enabled': False}},
        )
        body = self.client.get('/sw.js').content.decode()
        # OFFLINE_URL is blanked → the precache list is empty.
        self.assertIn("OFFLINE_URL = ''", body)

"""Agent-facing manifests carry the MERCHANT's brand, not the platform's.

Morpheus is the engine; the storefront belongs to the merchant. Every document
an AI client reads to decide who it is talking to — the UCP manifest, the
Trusted-Agent manifest, the MCP handshake, the ChatGPT-style plugin manifest —
must present `StoreSettings.store_name`.

These shipped hardcoded as `morpheus-ucp` / `Morpheus storefront` /
`support@morpheus.local`, so every store on the platform introduced itself to
shopping agents as a different business, with a contact address that does not
exist and a `logo_url` / `legal_info_url` that 404. Found while folding the
Montenegro fork back in (2026-09-18).
"""

from __future__ import annotations

import json

from django.test import Client, TestCase

from core.models import StoreSettings

BRAND = 'Montenegro Experience'


class ManifestBrandingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        StoreSettings.objects.all().delete()
        StoreSettings.objects.create(store_name=BRAND, contact_email='hello@example.com')

    def _json(self, url):
        response = Client().get(url)
        self.assertEqual(response.status_code, 200, url)
        return json.loads(response.content)

    def test_ucp_manifest_uses_the_store_name(self):
        data = self._json('/.well-known/ucp.json')
        self.assertEqual(data['name'], 'montenegro-experience-ucp')
        self.assertIn(BRAND, data['description'])
        self.assertNotIn('orpheus', json.dumps(data))

    def test_trusted_agent_manifest_uses_store_name_and_real_contact(self):
        data = self._json('/.well-known/agent.json')
        self.assertEqual(data['name'], 'montenegro-experience')
        self.assertEqual(data['contact'], 'hello@example.com')

    def test_plugin_manifest_is_branded_and_omits_what_is_unset(self):
        data = self._json('/mcp/v1/manifest.json')
        self.assertEqual(data['name_for_human'], BRAND)
        self.assertEqual(data['name_for_model'], 'montenegro_experience')
        self.assertEqual(data['contact_email'], 'hello@example.com')
        # No logo is configured, so the key is absent rather than pointing at
        # a placeholder that 404s.
        self.assertNotIn('logo_url', data)
        # /pages/terms/ is a 404; the cms page route is /p/<slug>/.
        self.assertTrue(data['legal_info_url'].endswith('/p/terms/'))

    def test_contact_is_omitted_when_the_merchant_has_not_set_one(self):
        """Telling an agent to mail an address that does not exist is worse
        than telling it nothing."""
        StoreSettings.objects.all().update(contact_email='')
        self.assertNotIn('contact', self._json('/.well-known/agent.json'))
        self.assertNotIn('contact_email', self._json('/mcp/v1/manifest.json'))

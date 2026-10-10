"""The UCP business profile is the one the specification describes.

``/.well-known/ucp.json`` shipped in v0.30.0, before the Universal Commerce
Protocol had a specification; it carries Morpheus's own keys (boolean
capabilities, an ``mcp`` endpoint map). An agent that reads the spec looks for
``/.well-known/ucp`` with ``ucp.version`` (a date), ``services`` keyed by
reverse-domain names (each entry with ``transport``, ``endpoint``, ``spec``),
``capabilities`` and ``payment_handlers``. The legacy file stays for the
clients that learned it; the spec-shaped profile sits beside it and claims only
what the store serves.
"""

from __future__ import annotations

import re

from django.test import Client, TestCase

from plugins.installed.agent_mcp.well_known import UCP_VERSION


class UcpProfileTests(TestCase):
    def test_the_profile_has_the_spec_shape(self):
        r = Client().get('/.well-known/ucp')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'].split(';')[0], 'application/json')
        data = r.json()
        ucp = data['ucp']
        self.assertRegex(ucp['version'], r'^\d{4}-\d{2}-\d{2}$')
        self.assertEqual(ucp['version'], UCP_VERSION)
        shopping = ucp['services']['dev.ucp.shopping']
        self.assertEqual(len(shopping), 1)
        entry = shopping[0]
        self.assertEqual(entry['transport'], 'mcp')
        self.assertEqual(entry['version'], UCP_VERSION)
        self.assertRegex(entry['endpoint'], r'^https?://.+/mcp/(cart|checkout)/v1/$')
        self.assertTrue(entry['spec'].startswith('https://ucp.dev/'))
        self.assertIsInstance(ucp['payment_handlers'], dict)
        self.assertIsInstance(ucp['capabilities'], dict)

    def test_no_capability_is_claimed_that_the_store_does_not_serve(self):
        # We offer the catalog, cart and checkout as MCP tools; the UCP
        # checkout *capability* (create_checkout / update_checkout /
        # complete_checkout over REST) is not implemented, so it is not claimed.
        ucp = Client().get('/.well-known/ucp').json()['ucp']
        self.assertNotIn('dev.ucp.shopping.checkout', ucp['capabilities'])

    def test_the_legacy_manifest_still_answers(self):
        data = Client().get('/.well-known/ucp.json').json()
        self.assertIn('capabilities', data)
        self.assertIn('productSearch', data['capabilities'])
        # And it points at the spec-shaped profile.
        self.assertTrue(data['profile_url'].endswith('/.well-known/ucp'))

    def test_the_profile_is_not_language_prefixed(self):
        # Machine endpoints register on the chrome surface, so i18n_patterns
        # never publishes /fr/.well-known/ucp.
        self.assertEqual(Client().get('/.well-known/ucp').status_code, 200)
        self.assertEqual(Client().get('/.well-known/ucp/').status_code, 404)

    def test_agent_json_links_the_profile(self):
        data = Client().get('/.well-known/agent.json').json()
        self.assertTrue(re.search(r'/\.well-known/ucp$', data['ucp_profile']))

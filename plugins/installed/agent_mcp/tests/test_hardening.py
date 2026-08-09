"""MCP safe-hardening regression tests.

Locks the resources/read governance parity fix: resources/read is a read alias
over the same tools tools/call exposes, so it must run the SAME scope gate.
Before the fix, a token scoped to only catalog.read could read
morpheus://catalog/featured (backed by products.search, which requires
system.read) with no scope check and no audit row.

(The test targets the products.search-backed resource on purpose:
analytics.summary is a colliding name — orders vs analytics register it with
different scopes — so its required scope is load-order-dependent and unfit for
an assertion; products.search has a single owner and a stable scope.)
"""

from __future__ import annotations

import json

from django.test import Client, TestCase

LEGACY = '/mcp/v1/'
_E_AUTH = -32001  # custom: needs auth / missing scope
_E_PARAMS = -32602  # invalid params (unknown resource uri)


def _rpc(method, params=None, _id=1):
    return json.dumps({'jsonrpc': '2.0', 'id': _id, 'method': method, 'params': params or {}})


class ResourcesReadGovernanceTests(TestCase):
    def setUp(self):
        from plugins.models import PluginConfig

        PluginConfig.objects.update_or_create(
            plugin_name='agent_mcp',
            defaults={
                'config': {
                    'public_keys': [
                        {'token': 'tok-sys', 'mcp_scopes': ['system.read']},
                        {'token': 'tok-cat', 'mcp_scopes': ['catalog.read']},
                    ]
                }
            },
        )
        self.c = Client()

    def _read(self, uri, token=None):
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'} if token else {}
        return self.c.post(
            LEGACY,
            data=_rpc('resources/read', {'uri': uri}),
            content_type='application/json',
            **headers,
        )

    def test_read_without_bearer_is_unauthenticated(self):
        r = self._read('morpheus://catalog/featured')
        self.assertEqual(r.json()['error']['code'], _E_AUTH)

    def test_underscoped_token_cannot_read_resource(self):
        # catalog.read lacks products.search's system.read scope — the same gate
        # tools/call runs must now block resources/read too.
        body = self._read('morpheus://catalog/featured', token='tok-cat').json()
        self.assertIn('error', body)
        self.assertEqual(body['error']['code'], _E_AUTH)
        self.assertIn('scope', body['error']['message'].lower())

    def test_correctly_scoped_token_reads_resource(self):
        body = self._read('morpheus://catalog/featured', token='tok-sys').json()
        # Scope gate crossed: a result, or a tool-level error — never auth/scope.
        if 'error' in body:
            self.assertNotEqual(body['error']['code'], _E_AUTH)
        else:
            self.assertIn('contents', body['result'])

    def test_unknown_resource_uri_is_rejected(self):
        body = self._read('morpheus://nope/x', token='tok-sys').json()
        self.assertEqual(body['error']['code'], _E_PARAMS)


class TrustedAgentOriginLockTests(TestCase):
    """The X-Verified-Agent-* headers must be ignored unless the request also
    carries the Cloudflare-injected shared secret (TRUSTED_AGENT_PROXY_SECRET)."""

    def _run(self, meta):
        from plugins.installed.agent_mcp.middleware import TrustedAgentMiddleware

        captured = {}

        def _get_response(request):
            captured['agent'] = request.trusted_agent
            from django.http import HttpResponse

            return HttpResponse('ok')

        from django.test import RequestFactory

        req = RequestFactory().get('/', **meta)
        TrustedAgentMiddleware(_get_response)(req)
        return captured['agent']

    def test_headers_ignored_when_secret_unconfigured(self):
        agent = self._run({'HTTP_X_VERIFIED_AGENT_ID': 'agent-123'})
        self.assertIsNone(agent)  # fail-closed by default

    def test_headers_ignored_when_secret_mismatches(self):
        with self.settings(TRUSTED_AGENT_PROXY_SECRET='s3cret'):
            agent = self._run(
                {
                    'HTTP_X_VERIFIED_AGENT_ID': 'agent-123',
                    'HTTP_X_VERIFIED_AGENT_ORIGIN_SECRET': 'wrong',
                }
            )
        self.assertIsNone(agent)

    def test_headers_trusted_with_matching_secret(self):
        with self.settings(TRUSTED_AGENT_PROXY_SECRET='s3cret'):
            agent = self._run(
                {
                    'HTTP_X_VERIFIED_AGENT_ID': 'agent-123',
                    'HTTP_X_VERIFIED_AGENT_ORIGIN_SECRET': 's3cret',
                }
            )
        self.assertIsNotNone(agent)
        self.assertEqual(agent.agent_id, 'agent-123')

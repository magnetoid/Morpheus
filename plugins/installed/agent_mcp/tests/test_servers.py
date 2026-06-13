"""MCP admin server — JSON-RPC happy path + Bearer-scope boundary.

The /mcp/admin/v1/ server is Bearer-gated and scope-enforced. These lock the
three boundary cases (anonymous, valid-but-under-scoped, correctly-scoped) plus
unauthenticated discovery — the agent surface's RBAC, previously untested.
"""

from __future__ import annotations

import json

from django.test import Client, TestCase

ADMIN = '/mcp/admin/v1/'
_E_AUTH = -32001


def _rpc(method, params=None, _id=1):
    return json.dumps({'jsonrpc': '2.0', 'id': _id, 'method': method, 'params': params or {}})


class McpAdminServerTests(TestCase):
    def setUp(self):
        from plugins.models import PluginConfig

        # Two scoped tokens + the curated reads. orders.search requires the
        # 'system.read' scope (core/assistant/tools/ecommerce.py).
        PluginConfig.objects.update_or_create(
            plugin_name='agent_mcp',
            defaults={
                'config': {
                    'public_keys': [
                        {'token': 'tok-scoped', 'mcp_scopes': ['system.read']},
                        {'token': 'tok-underscoped', 'mcp_scopes': ['catalog.read']},
                    ]
                }
            },
        )
        self.c = Client()

    def _post(self, body, token=None):
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'} if token else {}
        return self.c.post(ADMIN, data=body, content_type='application/json', **headers)

    def test_anonymous_tools_call_is_rejected(self):
        r = self._post(_rpc('tools/call', {'name': 'orders.search', 'arguments': {}}))
        self.assertEqual(r.status_code, 401)  # server-level Bearer gate
        self.assertEqual(r.json()['error']['code'], _E_AUTH)

    def test_underscoped_token_is_rejected(self):
        r = self._post(
            _rpc('tools/call', {'name': 'orders.search', 'arguments': {}}),
            token='tok-underscoped',
        )
        body = r.json()
        self.assertIn('error', body)
        self.assertEqual(body['error']['code'], _E_AUTH)
        self.assertIn('scope', body['error']['message'].lower())

    def test_correctly_scoped_token_passes_the_boundary(self):
        r = self._post(
            _rpc('tools/call', {'name': 'orders.search', 'arguments': {}}),
            token='tok-scoped',
        )
        body = r.json()
        # The scope gate is crossed: either a result, or a tool-level error —
        # but never the auth/scope error.
        if 'error' in body:
            self.assertNotEqual(body['error']['code'], _E_AUTH)
        else:
            self.assertIn('content', body['result'])

    def test_initialize_reports_authenticated_flag(self):
        r = self._post(_rpc('initialize'), token='tok-scoped')
        self.assertTrue(r.json()['result']['authenticated'])

    def test_unauthenticated_discovery_redacts_schema(self):
        # tools/list is reachable without a token but hides input schemas.
        r = self.c.post('/mcp/v1/', data=_rpc('tools/list'), content_type='application/json')
        tools = r.json()['result']['tools']
        self.assertTrue(tools)
        self.assertTrue(all(t.get('_auth_required') for t in tools))

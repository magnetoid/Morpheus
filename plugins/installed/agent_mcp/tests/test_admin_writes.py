"""Admin MCP write path (Wave 1 of docs/plans/cutting-edge-open-core-2026-07.md).

`_handle_tools_call` used to reject any tool outside the curated public-read
set BEFORE cluster resolution — so /mcp/admin/v1/ could LIST Linda's write
tools but never EXECUTE one, silently contradicting docs/MCP_SERVER.md and
the dashboard's approved_tools grants. Exposure now follows the active
cluster's whitelist (same resolution tools/list uses); every write still
passes scope → rate limit → approval → audit governance.
"""

from __future__ import annotations

import json

from django.core.cache import cache
from django.test import Client, TestCase

ADMIN = '/mcp/admin/v1/'
LEGACY = '/mcp/v1/'
_E_METHOD = -32601
_E_APPROVAL = -32030

WRITE_TOOL = 'orders.add_note'  # a real write in Linda's catalog (orders.write)


def _rpc(method, params=None, _id=1):
    return json.dumps({'jsonrpc': '2.0', 'id': _id, 'method': method, 'params': params or {}})


class AdminWritePathTests(TestCase):
    def setUp(self):
        from plugins.models import PluginConfig

        cache.clear()
        PluginConfig.objects.update_or_create(
            plugin_name='agent_mcp',
            defaults={
                'config': {
                    'public_keys': [
                        {
                            'token': 'tok-writer',
                            'label': 'ops-bot',
                            'mcp_scopes': ['orders.write'],
                            'approved_tools': [WRITE_TOOL],
                        },
                        {
                            'token': 'tok-ungranted',
                            'label': 'plain-bot',
                            'mcp_scopes': ['orders.write'],
                        },
                    ]
                }
            },
        )
        self.c = Client()

    def _call(self, endpoint, token, name, args=None):
        return self.c.post(
            endpoint,
            data=_rpc('tools/call', {'name': name, 'arguments': args or {}}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        ).json()

    def _tool(self):
        from plugins.installed.agent_mcp.servers import _clear_cluster, _set_cluster
        from plugins.installed.agent_mcp.views import _public_tools

        _set_cluster('admin', None)
        try:
            return next((t for t in _public_tools() if t.name == WRITE_TOOL), None)
        finally:
            _clear_cluster()

    def test_write_tool_is_reachable_on_admin_endpoint(self):
        """The old pre-check returned 'tool not exposed' (-32601) here — the
        call must now reach the tool (whose own confirmed=True two-step gate
        answers, rather than the exposure gate)."""
        self.assertIsNotNone(self._tool(), f'{WRITE_TOOL} missing from catalog')
        out = self._call(ADMIN, 'tok-writer', WRITE_TOOL, {'order_number': 'nope-1', 'note': 'x'})
        err = out.get('error') or {}
        self.assertNotEqual(err.get('code'), _E_METHOD, f'exposure gate still rejects: {err}')

    def test_ungranted_token_denied_when_tool_requires_approval(self):
        tool = self._tool()
        self.assertIsNotNone(tool)
        old = getattr(tool, 'requires_approval', False)
        tool.requires_approval = True
        self.addCleanup(setattr, tool, 'requires_approval', old)

        out = self._call(ADMIN, 'tok-ungranted', WRITE_TOOL, {'order_number': 'n-1', 'note': 'x'})
        self.assertEqual((out.get('error') or {}).get('code'), _E_APPROVAL)

    def test_write_tool_still_hidden_on_legacy_public_endpoint(self):
        out = self._call(LEGACY, 'tok-writer', WRITE_TOOL, {'order_number': 'n-1', 'note': 'x'})
        self.assertEqual((out.get('error') or {}).get('code'), _E_METHOD)

    def test_scopeless_token_cannot_write_on_admin(self):
        from plugins.models import PluginConfig

        cfg = PluginConfig.objects.get(plugin_name='agent_mcp')
        cfg.config['public_keys'].append(
            {'token': 'tok-reader', 'label': 'read-bot', 'mcp_scopes': ['system.read']}
        )
        cfg.save()
        out = self._call(ADMIN, 'tok-reader', WRITE_TOOL, {'order_number': 'n-1', 'note': 'x'})
        self.assertEqual((out.get('error') or {}).get('code'), -32001)  # missing scope

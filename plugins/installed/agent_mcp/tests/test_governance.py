"""MCP write governance (enterprise Phase 1): approval gate + audit + rate limit.

Previously a Bearer token with the right scope could execute ANY tool —
`requires_approval=True` was declared on ~58 tools but never enforced at the
MCP layer, no audit row recorded the call, and no rate limit applied. These
lock the three new behaviors at the `/mcp/admin/v1/` boundary:

  * a requires_approval tool is DENIED (-32030) unless the token entry carries
    the tool in `approved_tools` (the merchant's dashboard-made human decision);
  * every executed call writes an `agents.decision` core AuditEvent, and every
    denial writes `mcp.tool_denied`;
  * per-token rate limiting (-32029) with the limit taken from the token entry.
"""

from __future__ import annotations

import json

from django.core.cache import cache
from django.test import Client, TestCase

from core.audit.models import AuditEvent

ADMIN = '/mcp/admin/v1/'
_E_RATE = -32029
_E_APPROVAL = -32030

TOOL = 'orders.search'  # exposed on the admin cluster; scope system.read


def _rpc(method, params=None, _id=1):
    return json.dumps({'jsonrpc': '2.0', 'id': _id, 'method': method, 'params': params or {}})


class McpGovernanceTests(TestCase):
    def setUp(self):
        from plugins.models import PluginConfig

        cache.clear()  # rate-limit windows must not leak between tests
        PluginConfig.objects.update_or_create(
            plugin_name='agent_mcp',
            defaults={
                'config': {
                    'public_keys': [
                        {'token': 'tok-plain', 'label': 'partner', 'mcp_scopes': ['system.read']},
                        {
                            'token': 'tok-granted',
                            'label': 'trusted-bot',
                            'mcp_scopes': ['system.read'],
                            'approved_tools': [TOOL],
                        },
                        {
                            'token': 'tok-tight',
                            'label': 'throttled',
                            'mcp_scopes': ['system.read'],
                            'rate_limit_per_minute': 2,
                        },
                    ]
                }
            },
        )
        self.c = Client()

    def _call(self, token, name=TOOL, args=None):
        return self.c.post(
            ADMIN,
            data=_rpc('tools/call', {'name': name, 'arguments': args or {}}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        ).json()

    def _mark_approval_required(self):
        """Flip requires_approval on the live registry tool for this test."""
        from plugins.installed.agent_mcp.views import _public_tools

        tool = next(t for t in _public_tools() if t.name == TOOL)
        old = getattr(tool, 'requires_approval', False)
        tool.requires_approval = True
        self.addCleanup(setattr, tool, 'requires_approval', old)

    # ── Approval gate ───────────────────────────────────────────────────────

    def test_approval_tool_denied_without_grant(self):
        self._mark_approval_required()
        body = self._call('tok-plain')
        self.assertEqual(body['error']['code'], _E_APPROVAL)
        self.assertIn('approval required', body['error']['message'])
        deny = AuditEvent.objects.get(event_type='mcp.tool_denied')
        self.assertEqual(deny.actor_label, 'mcp:partner')
        self.assertEqual(deny.target, f'tool/{TOOL}')
        self.assertEqual(deny.metadata.get('reason'), 'approval_required')

    def test_approval_tool_allowed_with_grant(self):
        self._mark_approval_required()
        body = self._call('tok-granted')
        # Crosses the approval gate: a result or a tool-level error, never -32030.
        if 'error' in body:
            self.assertNotEqual(body['error']['code'], _E_APPROVAL)
        else:
            self.assertIn('content', body['result'])
        self.assertFalse(AuditEvent.objects.filter(event_type='mcp.tool_denied').exists())

    def test_plain_tool_unaffected_by_gate(self):
        body = self._call('tok-plain')  # requires_approval stays False
        if 'error' in body:
            self.assertNotIn(body['error']['code'], (_E_APPROVAL, _E_RATE))
        else:
            self.assertIn('content', body['result'])

    # ── Audit trail ─────────────────────────────────────────────────────────

    def test_executed_call_writes_agents_decision_row(self):
        self._call('tok-plain', args={'q': 'x'})
        ev = AuditEvent.objects.filter(event_type='agents.decision').latest('created_at')
        self.assertEqual(ev.actor_label, 'mcp:partner')
        self.assertEqual(ev.target, f'tool/{TOOL}')

    # ── Rate limiting ───────────────────────────────────────────────────────

    def test_per_token_rate_limit_enforced_and_audited(self):
        for _ in range(2):
            body = self._call('tok-tight')
            if 'error' in body:
                self.assertNotEqual(body['error']['code'], _E_RATE)
        third = self._call('tok-tight')
        self.assertEqual(third['error']['code'], _E_RATE)
        deny = AuditEvent.objects.filter(event_type='mcp.tool_denied').latest('created_at')
        self.assertIn('rate_limited', deny.metadata.get('reason', ''))
        # Other tokens are unaffected (separate buckets).
        body = self._call('tok-plain')
        if 'error' in body:
            self.assertNotEqual(body['error']['code'], _E_RATE)


class TrustedAgentAttributionTests(TestCase):
    """A verified-agent request that places an order stamps the agent id onto
    the order — the manifest advertises this ('persisted on checkout') and it
    was previously unwired (defined-but-never-called)."""

    def test_order_placed_stamps_agent_from_thread_local(self):
        from plugins.installed.agent_mcp.middleware import (
            TrustedAgent,
            _current,
            stamp_order_with_agent,
        )

        class _Order:
            def __init__(self):
                self.metadata = {}
                self.id = 'o1'
                self.saved = None

            def save(self, update_fields=None):
                self.saved = update_fields

        # No agent on the request → no-op.
        o = _Order()
        self.assertFalse(stamp_order_with_agent(o))
        self.assertEqual(o.metadata, {})

        # Middleware set the thread-local for this request → stamp lands.
        _current.agent = TrustedAgent(agent_id='agent-xyz', provider='visa')
        try:
            o2 = _Order()
            self.assertTrue(stamp_order_with_agent(o2))
            self.assertEqual(o2.metadata['agent_id'], 'agent-xyz')
            self.assertEqual(o2.metadata['agent_provider'], 'visa')
            self.assertIn('metadata', o2.saved)
        finally:
            _current.agent = None

    def test_plugin_subscribes_order_placed(self):
        # The ORDER_PLACED handler is what makes attribution automatic.
        from morpheus.core import MorpheusEvents, hook_registry

        handlers = [
            self._name(h) for h in hook_registry._handlers.get(MorpheusEvents.ORDER_PLACED, [])
        ]
        self.assertTrue(any('on_order_placed' in h for h in handlers))

    @staticmethod
    def _name(entry):
        fn = entry[1] if isinstance(entry, tuple) else entry
        return getattr(fn, '__qualname__', str(fn))

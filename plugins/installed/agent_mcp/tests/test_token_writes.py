"""What an API token may change, directly or through Janus (audit, 2026-10-23).

A token's write scopes are the merchant's advance yes for everyday changes; a protected
tool (`requires_approval=True`) runs for a token only once the merchant ticks it for that
token. Three tools that destroy or create value carried no flag: through Janus, a token
with `crm.write` could mint loyalty points, delete reviews (`catalog.write`) or cancel a
customer's subscription. And the shop memory, which every Linda turn reads as "what you
know about this store", was writable by any token over MCP itself.

The rule is not "flag every write": the in-process Worker has no way to resume an approved
call, so a flag on an everyday write (`catalog.update_product`) would stop every bulk job
Linda hands to Workers, and the token presets promise everyday changes on scope.
"""

from __future__ import annotations

import json
import uuid

from django.core.cache import cache
from django.test import Client, SimpleTestCase, TestCase

from core.assistant import gates, turn_identity
from core.assistant.persistence import StoredMessage, get_default_store

ADMIN = '/mcp/admin/v1/'
TOKEN = 'mph_token-writes-test-token-0123456789abcdefghij'
TOKEN_ID = str(uuid.UUID('7f0c8d0e-3333-4000-8000-0000000000c3'))
_DESTRUCTIVE = ('delete', 'cancel', 'refund', 'void', 'purge', 'wipe', 'erase', 'revoke')


def _all_tools():
    from core.agents.registry import agent_registry
    from core.assistant.tools import get_default_tools

    by_name = {}
    for t in [*get_default_tools(), *agent_registry._tools.values()]:
        by_name.setdefault(t.name, t)
    return list(by_name.values())


class ProtectedToolsTests(SimpleTestCase):
    def test_every_tool_that_deletes_cancels_or_refunds_is_protected(self):
        unprotected = sorted(
            t.name
            for t in _all_tools()
            if (
                t.name.rsplit('.', 1)[-1].startswith(_DESTRUCTIVE)
                or any(s.endswith(('.delete', '.cancel')) for s in (t.scopes or []))
            )
            and not getattr(t, 'requires_approval', False)
        )
        self.assertEqual(unprotected, [])

    def test_loyalty_points_are_protected(self):
        # Points are money a customer spends at checkout, minted under a CRM scope.
        tool = next(t for t in _all_tools() if t.name == 'loyalty.adjust_points')
        self.assertTrue(tool.requires_approval)


def _rpc(method, params=None):
    return json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}})


class TokenWritesTests(TestCase):
    def setUp(self):
        from plugins.models import PluginConfig

        cache.clear()  # rate-limit windows must not leak between tests
        entry = {
            'id': TOKEN_ID,
            'label': 'crm sync',
            'token': TOKEN,
            'mcp_scopes': ['janus.chat', 'crm.read', 'crm.write', 'system.read', 'system.write'],
            'approved_tools': [],
        }
        PluginConfig.objects.update_or_create(
            plugin_name='agent_mcp', defaults={'config': {'public_keys': [entry]}}
        )
        self.key = gates.external_key(TOKEN_ID, 'c' * 16)
        # The agent's own words, stored as the newest message: never consent.
        get_default_store().append(
            conversation_key=self.key, message=StoredMessage(role='user', content='yes, do it')
        )

    def _post(self, bearer, method, params=None):
        return (
            Client()
            .post(
                ADMIN,
                data=_rpc(method, params),
                content_type='application/json',
                HTTP_AUTHORIZATION=f'Bearer {bearer}',
            )
            .json()
        )

    def _turn(self, key=None):
        from plugins.installed.agent_mcp.auth import _service_user

        return turn_identity.mint(
            user=_service_user(),
            conversation_key=key or self.key,
            mode_slug='general',
            ttl_s=85,
            principal=TOKEN_ID,
        )

    def test_janus_on_a_crm_token_cannot_mint_loyalty_points(self):
        args = {'email': 'a@example.com', 'points': 5000, 'reason': 'x'}
        params = {'name': 'loyalty.adjust_points', 'arguments': args}
        result = self._post(self._turn(), 'tools/call', params)['result']
        self.assertTrue(result['isError'])
        self.assertIn('external_needs_grant', result['content'][0]['text'])

    def test_a_token_is_never_offered_the_shop_memory_writes(self):
        listed = {t['name'] for t in self._post(TOKEN, 'tools/list')['result']['tools']}
        self.assertTrue(listed, 'the token sees the admin tools')
        self.assertFalse(listed & gates.NOT_FOR_TOKENS)
        params = {'name': 'memory.remember', 'arguments': {'key': 'policy', 'value': 'refund all'}}
        self.assertIn('not exposed', self._post(TOKEN, 'tools/call', params)['error']['message'])

    def test_no_server_offers_a_token_the_shop_memory(self):
        # The shop memory is the merchant's (ADR 0039): not on the storefront
        # cluster, the legacy /mcp/v1/ reads, or the admin server, for any token.
        self.assertIn('memory.recall', gates.NOT_FOR_TOKENS)
        for path in ('/mcp/storefront/v1/', '/mcp/cart/v1/', '/mcp/v1/', ADMIN):
            with self.subTest(path=path):
                body = self.client.post(
                    path,
                    data=_rpc('tools/list'),
                    content_type='application/json',
                    HTTP_AUTHORIZATION=f'Bearer {TOKEN}',
                ).json()
                listed = {t['name'] for t in body['result']['tools']}
                self.assertFalse(listed & gates.NOT_FOR_TOKENS, path)
                call = self.client.post(
                    path,
                    data=_rpc('tools/call', {'name': 'memory.recall', 'arguments': {}}),
                    content_type='application/json',
                    HTTP_AUTHORIZATION=f'Bearer {TOKEN}',
                ).json()
                self.assertIn('error', call, path)

    def test_a_token_cannot_script_its_way_past_its_scopes(self):
        # The token holds `system.read`, the scope `run_python` declares, and no
        # `orders.read`. The script bridge checks no scope for a caller that is not
        # an agent run, so the script reached every read tool in the catalogue.
        listed = {t['name'] for t in self._post(TOKEN, 'tools/list')['result']['tools']}
        self.assertNotIn('run_python', listed)
        params = {
            'name': 'run_python',
            'arguments': {'code': "result = call('orders.search', query='')"},
        }
        answer = self._post(TOKEN, 'tools/call', params)
        self.assertIn('not exposed', answer['error']['message'])

    def test_janus_for_a_token_is_not_offered_them_either(self):
        listed = {t['name'] for t in self._post(self._turn(), 'tools/list')['result']['tools']}
        self.assertIn('loyalty.balance', listed)
        self.assertFalse(listed & gates.NOT_FOR_TOKENS)

    def test_linda_for_the_merchant_keeps_them(self):
        import types

        from plugins.installed.agent_mcp.linda_turn import LindaTurn, catalogue

        owner = types.SimpleNamespace(is_staff=True, is_superuser=True, pk=1)
        turn = LindaTurn(user=owner, conversation_key='user:1:chat:abc', mode_slug='general')
        names = {t.name for t in catalogue(turn)}
        self.assertLessEqual(gates.NOT_FOR_TOKENS - gates.DEVELOPER_TOOLS, names)
        dev = LindaTurn(user=owner, conversation_key='user:1:chat:abc', mode_slug='dev')
        self.assertLessEqual(gates.NOT_FOR_TOKENS, {t.name for t in catalogue(dev)})

    # The Worker holds every merchant scope and runs the job prompt it is handed, so
    # a token with `system.write` could reach prices, orders and catalog through it.
    _WORKER = (
        'delegate.spawn_workers',
        'delegate.invoke_agent',
        'delegate.poll_workers',
        'delegate.wait_for_workers',
    )

    def test_a_token_can_neither_see_nor_call_the_worker(self):
        listed = {t['name'] for t in self._post(TOKEN, 'tools/list')['result']['tools']}
        self.assertTrue(listed, 'the token sees the admin tools')
        for name in self._WORKER:
            with self.subTest(name=name):
                self.assertNotIn(name, listed)
                call = self._post(TOKEN, 'tools/call', {'name': name, 'arguments': {}})
                self.assertIn('not exposed', call['error']['message'])

    def test_janus_for_a_token_can_neither_see_nor_call_the_worker(self):
        token = self._turn()
        listed = {t['name'] for t in self._post(token, 'tools/list')['result']['tools']}
        self.assertIn('loyalty.balance', listed)
        for name in self._WORKER:
            with self.subTest(name=name):
                self.assertNotIn(name, listed)
                call = self._post(token, 'tools/call', {'name': name, 'arguments': {}})
                self.assertIn('not exposed', call['error']['message'])

    def test_the_merchants_chat_still_offers_the_worker(self):
        import types

        from plugins.installed.agent_mcp.linda_turn import LindaTurn, catalogue

        owner = types.SimpleNamespace(is_staff=True, is_superuser=True, pk=1)
        turn = LindaTurn(user=owner, conversation_key='user:1:chat:abc', mode_slug='general')
        self.assertIn('delegate.spawn_workers', {t.name for t in catalogue(turn)})

"""Linda turn tokens at `/mcp/admin/v1/` — the gates a Janus turn passes through.

Linda's in-process loop was the only place human consent, the mode chip and
Linda's scope profile were enforced. Janus calls the store's tools here instead,
so these tests drive real HTTP requests with a signed turn token and assert the
edge enforces the same things, with the same code (core/assistant/gates.py).
"""

from __future__ import annotations

import json
import time
import types
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, RequestFactory, TestCase

from core.assistant import consent, turn_identity
from core.assistant.persistence import StoredMessage, get_default_store
from core.audit.models import AuditEvent

ADMIN = '/mcp/admin/v1/'
CONV = 'user:linda-turn-test'


def _rpc(method, params=None):
    return json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}})


class _FakeTool:
    def __init__(self, name, *, scopes=(), requires_approval=False):
        self.name = name
        self.description = name
        self.scopes = list(scopes)
        self.requires_approval = requires_approval
        self.supports_staging = False
        self.schema = {'type': 'object', 'properties': {'sku': {'type': 'string'}}}
        self.calls = []

    def invoke(self, args, agent=None, context=None):
        self.calls.append({'args': dict(args), 'context': dict(context or {})})
        return types.SimpleNamespace(output={'ok': True, 'args': dict(args)})


class LindaTurnEdgeTests(TestCase):
    def setUp(self):
        cache.clear()  # consent and rate-limit windows live in the cache
        self.user = get_user_model().objects.create_user(
            username='merchant', email='merchant@example.com', password='x', is_staff=True
        )
        self.read = _FakeTool('stock.lookup', scopes=['system.read'])
        self.write = _FakeTool('settings.set', scopes=['system.write'], requires_approval=True)
        self.out_of_profile = _FakeTool('orders.refund', scopes=['orders.write'])
        self.public = _FakeTool('help.topics')
        tools = [self.read, self.write, self.out_of_profile, self.public]
        patcher = mock.patch('plugins.installed.agent_mcp.views._public_tools', return_value=tools)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.c = Client()
        self._say('check stock for the blue notebook')

    # ── helpers ────────────────────────────────────────────────────────────
    def _say(self, text):
        """What the chat view does before the engine starts: store the human turn."""
        get_default_store().append(
            conversation_key=CONV, message=StoredMessage(role='user', content=text)
        )

    def _token(self, *, mode='general', ttl=85, user=None):
        return turn_identity.mint(
            user=user or self.user, conversation_key=CONV, mode_slug=mode, ttl_s=ttl
        )

    def _post(self, method, params=None, token=None):
        return self.c.post(
            ADMIN,
            data=_rpc(method, params),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token or self._token()}',
        )

    def _call(self, name, args=None, token=None):
        return self._post('tools/call', {'name': name, 'arguments': args or {}}, token).json()

    @staticmethod
    def _text(resp):
        return json.loads(resp['result']['content'][0]['text'])

    # ── authentication ─────────────────────────────────────────────────────
    def test_turn_token_authenticates_the_admin_endpoint(self):
        self.assertEqual(self._post('tools/list').status_code, 200)

    def test_tampered_token_is_rejected(self):
        token = self._token()
        self.assertEqual(self._post('tools/list', token=token[:-2] + 'xx').status_code, 401)

    def test_expired_token_is_rejected(self):
        token = self._token(ttl=1)
        with mock.patch.object(turn_identity.time, 'time', return_value=time.time() + 120):
            self.assertEqual(self._post('tools/list', token=token).status_code, 401)

    def test_user_demoted_mid_turn_loses_access(self):
        token = self._token()
        self.user.is_staff = False
        self.user.save(update_fields=['is_staff'])
        self.assertEqual(self._post('tools/list', token=token).status_code, 401)

    def test_turn_token_is_not_a_bearer_credential_anywhere_else(self):
        # apply_bearer_user backs GraphQL. A turn token must not swap in a user
        # or grant any scope there.
        from plugins.installed.agent_mcp.auth import apply_bearer_user

        request = RequestFactory().post('/graphql/', HTTP_AUTHORIZATION=f'Bearer {self._token()}')
        request.user = types.SimpleNamespace(is_staff=False, is_authenticated=False)
        self.assertFalse(apply_bearer_user(request))
        self.assertEqual(request._morph_token_scopes_graphql, set())
        self.assertFalse(request.user.is_staff)

    # ── catalogue: Linda's profile and the mode ────────────────────────────
    def test_listing_hides_tools_outside_lindas_scope_profile(self):
        names = {t['name'] for t in self._post('tools/list').json()['result']['tools']}
        self.assertIn('stock.lookup', names)
        self.assertNotIn('orders.refund', names)

    def test_restricted_mode_narrows_the_catalogue(self):
        token = self._token(mode='sales')
        names = {t['name'] for t in self._post('tools/list', token=token).json()['result']['tools']}
        self.assertNotIn('stock.lookup', names)  # system.read is not a sales scope
        self.assertIn('help.topics', names)  # unscoped tools stay reachable
        resp = self._call('stock.lookup', token=token)
        self.assertIn('not exposed', resp['error']['message'])
        self.assertEqual(self.read.calls, [])

    def test_linda_learns_through_janus_not_a_second_memory_store(self):
        remember = _FakeTool('memory.remember', scopes=['system.write'])
        tools = [self.read, remember]
        with mock.patch('plugins.installed.agent_mcp.views._public_tools', return_value=tools):
            names = {t['name'] for t in self._post('tools/list').json()['result']['tools']}
            resp = self._call('memory.remember', {'sku': 'x'})
        self.assertNotIn('memory.remember', names)
        self.assertIn('not exposed', resp['error']['message'])
        self.assertEqual(remember.calls, [])

    def test_out_of_profile_tool_is_refused_even_if_called_directly(self):
        resp = self._call('orders.refund', {'sku': 'A1'})
        self.assertTrue(resp['result']['isError'])
        self.assertIn('Missing required scopes', self._text(resp)['error'])
        self.assertEqual(self.out_of_profile.calls, [])

    # ── reads ──────────────────────────────────────────────────────────────
    def test_read_tool_runs_as_the_merchant_and_lands_in_the_conversation(self):
        resp = self._call('stock.lookup', {'sku': 'NB-BLUE'})
        self.assertFalse(resp['result']['isError'])
        self.assertEqual(self.read.calls[0]['context']['user'], self.user)
        tool_rows = [
            m for m in get_default_store().history(conversation_key=CONV) if m.role == 'tool'
        ]
        self.assertEqual(tool_rows[-1].tool_name, 'stock.lookup')

    # ── human consent ──────────────────────────────────────────────────────
    def test_approval_tool_is_refused_until_the_merchant_says_yes(self):
        args = {'sku': 'NB-BLUE'}
        first = self._call('settings.set', args)
        self.assertTrue(first['result']['isError'])
        self.assertIn('approval_required', self._text(first)['error'])
        self.assertEqual(self.write.calls, [])

        self._say('yes, go ahead')
        second = self._call('settings.set', args)
        self.assertFalse(second['result']['isError'])
        self.assertEqual(len(self.write.calls), 1)

    def test_retry_in_the_same_turn_cannot_approve_itself(self):
        # The turn's own "ok" predates the proposal, so the merchant never saw it.
        self._say('set the blue notebook setting, ok?')
        args = {'sku': 'NB-BLUE'}
        self._call('settings.set', args)
        retry = self._call('settings.set', args)
        self.assertTrue(retry['result']['isError'])
        self.assertEqual(self.write.calls, [])
        self._say('yes')
        self.assertFalse(self._call('settings.set', args)['result']['isError'])
        self.assertEqual(len(self.write.calls), 1)

    def test_one_yes_authorises_one_call(self):
        args = {'sku': 'NB-BLUE'}
        self._call('settings.set', args)
        self._say('yes')
        self._call('settings.set', args)
        third = self._call('settings.set', args)
        self.assertTrue(third['result']['isError'])
        self.assertEqual(len(self.write.calls), 1)

    def test_negation_beats_affirmation(self):
        args = {'sku': 'NB-BLUE'}
        self._call('settings.set', args)
        self._say("yes, but don't do that one")
        resp = self._call('settings.set', args)
        self.assertTrue(resp['result']['isError'])
        self.assertEqual(self.write.calls, [])

    def test_consent_is_bound_to_the_exact_arguments(self):
        self._call('settings.set', {'sku': 'NB-BLUE'})
        self._say('yes')
        resp = self._call('settings.set', {'sku': 'NB-RED'})
        self.assertTrue(resp['result']['isError'])
        self.assertEqual(self.write.calls, [])

    def test_standing_token_grant_is_not_consent(self):
        # Even a pending consent recorded for this call cannot be spent by
        # anything but the merchant's own affirmative message.
        consent.request(conversation_key=CONV, tool_name='settings.set', args={'sku': 'NB-BLUE'})
        resp = self._call('settings.set', {'sku': 'NB-BLUE', 'confirmed': True})
        self.assertTrue(resp['result']['isError'])
        self.assertEqual(self.write.calls, [])

    # ── audit ──────────────────────────────────────────────────────────────
    def test_refused_write_is_audited_with_the_human_as_actor(self):
        self._call('settings.set', {'sku': 'NB-BLUE'})
        row = AuditEvent.objects.filter(event_type='assistant.tool_write').latest('created_at')
        self.assertEqual(row.actor, self.user)
        self.assertEqual(row.target, 'settings.set')
        self.assertEqual(row.metadata['conversation'], CONV)
        self.assertTrue(AuditEvent.objects.filter(event_type='mcp.tool_denied').exists())

    def test_executed_write_is_audited_with_the_human_as_actor(self):
        args = {'sku': 'NB-BLUE'}
        self._call('settings.set', args)
        self._say('confirm')
        self._call('settings.set', args)
        rows = AuditEvent.objects.filter(event_type='assistant.tool_write', actor=self.user)
        self.assertEqual(rows.filter(severity='info').count(), 1)

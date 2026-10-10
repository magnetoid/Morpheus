"""External agents talk to Janus (docs/plans/janus-external-agents-2026-10.md, ADR 0039).

Janus does for an external agent exactly what that agent's token could do itself:
the token's scopes, the protected tools the merchant approved for it, and nothing
said in the conversation is consent. The door opens only for a token that lists
``janus.chat`` explicitly. Janus's engine is faked at ``run_turn``; the gates and
the edge are exercised for real.
"""

from __future__ import annotations

import json
import time
import types
import uuid
from unittest import mock

from django.core.cache import cache
from django.test import Client, TestCase

from core.assistant import gates, turn_identity
from core.assistant.persistence import StoredMessage, get_default_store

ADMIN = '/mcp/admin/v1/'
TOKEN = 'mph_janus-door-test-token-0123456789abcdefghij'
TOKEN_ID = str(uuid.UUID('7f0c8d0e-1111-4000-8000-0000000000a1'))
OTHER = 'mph_janus-door-other-token-0123456789abcdefghij'
OTHER_ID = str(uuid.UUID('7f0c8d0e-2222-4000-8000-0000000000b2'))


def _entry(**over) -> dict:
    entry = {
        'id': TOKEN_ID,
        'label': 'Hermes on the laptop',
        'token': TOKEN,
        'mcp_scopes': ['janus.chat', 'catalog.read', 'catalog.write'],
        'graphql_scopes': ['janus.chat'],
        'approved_tools': [],
    }
    entry.update(over)
    return entry


def _store_tokens(*entries) -> None:
    from plugins.models import PluginConfig

    PluginConfig.objects.update_or_create(
        plugin_name='agent_mcp', defaults={'config': {'public_keys': list(entries)}}
    )


def _rpc(method, params=None) -> str:
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
        self.calls.append(dict(args))
        return types.SimpleNamespace(output={'ok': True})


class ExternalGateTests(TestCase):
    """core/assistant/gates.py — the one gate chain, for an external conversation."""

    def setUp(self):
        cache.clear()
        self.key = gates.external_key(TOKEN_ID, 'a' * 16)
        self.protected = _FakeTool('prices.set', scopes=['catalog.write'], requires_approval=True)
        self.write = _FakeTool('products.rename', scopes=['catalog.write'])

    def _reason(self, tool, *, approved=frozenset(), scopes=('catalog.write',)):
        return gates.gate_reason(
            tool=tool,
            tool_name=tool.name,
            args={'sku': 'X-1'},
            scopes=list(scopes),
            context={},
            conversation_key=self.key,
            human_message='yes, go ahead',
            human_message_at=time.time() + 60,
            needs_consent=True,
            external_approved=approved,
        )

    def test_the_keys_name_their_token(self):
        self.assertEqual(self.key, f'ext:{TOKEN_ID}:chat:{"a" * 16}')
        self.assertTrue(gates.is_external_key(self.key))
        self.assertEqual(gates.principal_of(self.key), TOKEN_ID)
        self.assertFalse(gates.is_external_key('user:5:chat:abc'))
        self.assertEqual(gates.principal_of('user:5'), '')

    def test_a_yes_in_the_conversation_is_never_consent(self):
        with (
            mock.patch('core.assistant.consent.consume') as consume,
            mock.patch('core.assistant.consent.request') as request,
        ):
            reason = self._reason(self.protected)
        self.assertTrue(reason.startswith('external_needs_grant'), reason)
        consume.assert_not_called()
        request.assert_not_called()  # nothing pending, so nothing can approve it later

    def test_a_protected_tool_the_merchant_approved_for_the_token_runs(self):
        self.assertIsNone(self._reason(self.protected, approved=frozenset({'prices.set'})))

    def test_a_write_inside_the_tokens_scopes_runs(self):
        self.assertIsNone(self._reason(self.write))

    def test_the_scope_check_still_comes_first(self):
        reason = self._reason(self.write, scopes=('catalog.read',))
        self.assertIsNotNone(reason)
        self.assertFalse(reason.startswith('external_'))

    def test_an_external_key_without_a_grant_set_is_refused(self):
        self.assertTrue(self._reason(self.write, approved=None).startswith('external_'))


class TurnPrincipalTests(TestCase):
    def test_a_turn_token_carries_its_principal(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username='svc', email='svc@x.test', password='x', is_staff=True
        )
        token = turn_identity.mint(
            user=user,
            conversation_key=gates.external_key(TOKEN_ID, 'c' * 16),
            mode_slug='general',
            ttl_s=60,
            principal=TOKEN_ID,
        )
        self.assertEqual(turn_identity.verify(token).principal, TOKEN_ID)
        plain = turn_identity.mint(
            user=user, conversation_key='user:1', mode_slug='general', ttl_s=60
        )
        self.assertEqual(turn_identity.verify(plain).principal, '')

    def test_the_runtime_mints_the_principal_it_is_given(self):
        from core.assistant.runtime import Assistant
        from plugins.installed.agent_mcp.auth import _service_user

        key = gates.external_key(TOKEN_ID, 'd' * 16)
        token = Assistant()._mint_turn_token(
            {'user': _service_user(), 'mode': 'general', 'principal': TOKEN_ID}, key
        )
        self.assertEqual(turn_identity.verify(token).principal, TOKEN_ID)


class ExternalEdgeTests(TestCase):
    """The MCP edge holds an external turn to its token, looked up on every call."""

    def setUp(self):
        cache.clear()
        from plugins.installed.agent_mcp.auth import _service_user

        self.user = _service_user()
        _store_tokens(_entry())
        self.key = gates.external_key(TOKEN_ID, 'b' * 16)
        self.read = _FakeTool('products.lookup', scopes=['catalog.read'])
        self.write = _FakeTool('products.rename', scopes=['catalog.write'])
        self.protected = _FakeTool(
            'products.reprice', scopes=['catalog.write'], requires_approval=True
        )
        self.orders = _FakeTool('orders.peek', scopes=['orders.read'])
        self.tools = [self.read, self.write, self.protected, self.orders]
        patcher = mock.patch(
            'plugins.installed.agent_mcp.linda_turn._all_tools', side_effect=lambda: self.tools
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        # The agent's own words, stored as the newest message: never consent.
        get_default_store().append(
            conversation_key=self.key, message=StoredMessage(role='user', content='yes, do it')
        )
        self.c = Client()

    def _token(self, *, principal=TOKEN_ID, key=None):
        return turn_identity.mint(
            user=self.user,
            conversation_key=key or self.key,
            mode_slug='general',
            ttl_s=85,
            principal=principal,
        )

    def _post(self, method, params=None, token=None):
        return self.c.post(
            ADMIN,
            data=_rpc(method, params),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token or self._token()}',
        )

    def _call(self, name):
        resp = self._post('tools/call', {'name': name, 'arguments': {'sku': 'X-1'}}).json()
        return resp['result']

    def test_the_catalogue_is_the_tokens_scopes(self):
        names = {t['name'] for t in self._post('tools/list').json()['result']['tools']}
        self.assertEqual(names, {'products.lookup', 'products.rename', 'products.reprice'})

    def test_a_write_inside_the_scopes_runs(self):
        self.assertFalse(self._call('products.rename')['isError'])
        self.assertEqual(len(self.write.calls), 1)

    def test_a_protected_write_needs_the_tokens_approval_not_a_yes(self):
        refused = self._call('products.reprice')
        self.assertTrue(refused['isError'])
        self.assertIn('external_needs_grant', refused['content'][0]['text'])
        self.assertEqual(self.protected.calls, [])
        _store_tokens(_entry(approved_tools=['products.reprice']))
        self.assertFalse(self._call('products.reprice')['isError'])
        self.assertEqual(len(self.protected.calls), 1)

    def test_a_revoked_token_stops_the_turn(self):
        token = self._token()
        _store_tokens()
        self.assertEqual(self._post('tools/list', token=token).status_code, 401)

    def test_a_principal_that_does_not_own_the_conversation_is_refused(self):
        _store_tokens(_entry(), _entry(id=OTHER_ID, token=OTHER))
        token = self._token(principal=OTHER_ID)
        self.assertEqual(self._post('tools/list', token=token).status_code, 401)

    def test_a_dashboard_conversation_cannot_carry_a_principal(self):
        token = self._token(key='user:5:chat:abcdef')
        self.assertEqual(self._post('tools/list', token=token).status_code, 401)


def _fake_outcome(**over) -> dict:
    out = {'text': 'Best seller this week: the wind-up radio.', 'state': 'completed', 'error': ''}
    out['tool_calls'] = 2
    out.update(over)
    return out


class JanusDoorMcpTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        _store_tokens(_entry(), _entry(id=OTHER_ID, token=OTHER, label='Script'))
        patcher = mock.patch('core.assistant.external.run_turn', return_value=_fake_outcome())
        self.run_turn = patcher.start()
        self.addCleanup(patcher.stop)
        self.c = Client()

    def _post(self, method, params=None, token=TOKEN):
        return self.c.post(
            ADMIN,
            data=_rpc(method, params),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

    def _ask(self, args, token=TOKEN) -> dict:
        resp = self._post('tools/call', {'name': 'janus.ask', 'arguments': args}, token).json()
        return json.loads(resp['result']['content'][0]['text'])

    def test_tools_list_offers_the_door(self):
        names = {t['name'] for t in self._post('tools/list').json()['result']['tools']}
        self.assertTrue({'janus.ask', 'janus.reply'} <= names)

    def test_janus_answers_a_question(self):
        from plugins.installed.agent_mcp.auth import _service_user

        answer = self._ask({'message': 'What sold best this week?'})
        self.assertEqual(answer['status'], 'done')
        self.assertEqual(answer['reply'], 'Best seller this week: the wind-up radio.')
        self.assertRegex(answer['conversation'], r'^[0-9a-f]{16}$')
        self.assertRegex(answer['turn'], r'^[0-9a-f]{24}$')
        kwargs = self.run_turn.call_args.kwargs
        self.assertEqual(kwargs['principal'], TOKEN_ID)
        self.assertEqual(
            kwargs['conversation_key'], gates.external_key(TOKEN_ID, answer['conversation'])
        )
        self.assertEqual(kwargs['user'], _service_user())

    def test_a_conversation_continues_under_its_own_key(self):
        first = self._ask({'message': 'Hello'})
        self._ask({'message': 'And the week before?', 'conversation': first['conversation']})
        keys = [c.kwargs['conversation_key'] for c in self.run_turn.call_args_list]
        self.assertEqual(keys[0], keys[1])

    def test_a_token_without_the_grant_is_refused(self):
        _store_tokens(_entry(mcp_scopes=['*']))
        answer = self._ask({'message': 'Hello'})
        self.assertEqual((answer['status'], answer['code']), ('refused', 'forbidden'))
        self.run_turn.assert_not_called()

    def test_a_legacy_token_without_scopes_is_refused(self):
        legacy = _entry()
        del legacy['mcp_scopes']
        _store_tokens(legacy)
        self.assertEqual(self._ask({'message': 'Hello'})['status'], 'refused')

    def test_janus_cannot_call_itself(self):
        from plugins.installed.agent_mcp.auth import _service_user
        from plugins.installed.agent_mcp.linda_turn import LindaTurn, catalogue

        turn = LindaTurn(user=_service_user(), conversation_key='user:1', mode_slug='dev')
        self.assertFalse(any(t.name.startswith('janus.') for t in catalogue(turn)))


class JanusDoorServiceTests(TestCase):
    """The door's own rules, called directly (the queue is stubbed to stay pending)."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        _store_tokens(_entry(), _entry(id=OTHER_ID, token=OTHER))
        from plugins.installed.agent_mcp import janus_door

        self.door = janus_door
        delay = mock.patch('plugins.installed.agent_mcp.tasks.janus_turn.delay')
        self.delay = delay.start()
        self.addCleanup(delay.stop)

    def test_a_running_turn_is_fetched_later(self):
        pending = self.door.ask(entry=_entry(), message='Audit the shop', wait_seconds=0)
        self.assertEqual(pending['status'], 'queued')
        self.assertIn('hint', pending)
        turn_id, message = self.delay.call_args.args
        with mock.patch('core.assistant.external.run_turn', return_value=_fake_outcome()):
            self.assertEqual(self.door.run(turn_id, message), 'done')
        answer = self.door.reply(entry=_entry(), turn=pending['turn'], wait_seconds=0)
        self.assertEqual(answer['status'], 'done')

    def test_another_token_cannot_read_a_turn(self):
        pending = self.door.ask(entry=_entry(), message='Hello', wait_seconds=0)
        with self.assertRaises(self.door.DoorError) as caught:
            self.door.reply(
                entry=_entry(id=OTHER_ID, token=OTHER), turn=pending['turn'], wait_seconds=0
            )
        self.assertEqual(caught.exception.code, 'not_found')

    def test_two_running_questions_is_the_limit(self):
        for _ in range(self.door.RUNNING_MAX):
            self.door.ask(entry=_entry(), message='Hello', wait_seconds=0)
        with self.assertRaises(self.door.DoorError) as caught:
            self.door.ask(entry=_entry(), message='One more', wait_seconds=0)
        self.assertEqual(caught.exception.code, 'busy')

    def test_too_many_questions_a_minute_are_refused(self):
        with (
            mock.patch.object(self.door, 'TURNS_PER_MINUTE', 1),
            mock.patch.object(self.door, 'RUNNING_MAX', 5),
        ):
            self.door.ask(entry=_entry(), message='Hello', wait_seconds=0)
            with self.assertRaises(self.door.DoorError) as caught:
                self.door.ask(entry=_entry(), message='Again', wait_seconds=0)
        self.assertEqual(caught.exception.code, 'rate_limited')

    def test_a_turn_whose_worker_died_is_reported_lost(self):
        pending = self.door.ask(entry=_entry(), message='Hello', wait_seconds=0)
        state = cache.get(self.door._turn_key(pending['turn']))
        state['created_at'] = time.time() - self.door.STALE_AFTER_S - 5
        cache.set(self.door._turn_key(pending['turn']), state, 60)
        answer = self.door.reply(entry=_entry(), turn=pending['turn'], wait_seconds=0)
        self.assertEqual(answer['status'], 'failed')

    def test_a_token_revoked_before_the_turn_runs_is_not_run(self):
        pending = self.door.ask(entry=_entry(), message='Hello', wait_seconds=0)
        turn_id, message = self.delay.call_args.args
        _store_tokens()
        with mock.patch('core.assistant.external.run_turn') as run_turn:
            self.assertEqual(self.door.run(turn_id, message), 'failed')
        run_turn.assert_not_called()
        self.assertEqual(pending['status'], 'queued')


class JanusDoorGraphqlTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        _store_tokens(_entry())
        patcher = mock.patch('core.assistant.external.run_turn', return_value=_fake_outcome())
        self.run_turn = patcher.start()
        self.addCleanup(patcher.stop)
        self.c = Client(enforce_csrf_checks=True)

    def _gql(self, query, variables=None, token=TOKEN):
        resp = self.c.post(
            '/graphql/',
            data=json.dumps({'query': query, 'variables': variables or {}}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        return resp.json()['data']

    ASK = 'mutation($m:String!){askJanus(input:{message:$m}){status reply conversation turn error}}'

    def test_ask_janus_answers(self):
        data = self._gql(self.ASK, {'m': 'What sold best?'})
        self.assertEqual(data['askJanus']['status'], 'done')
        self.assertIn('wind-up radio', data['askJanus']['reply'])

    def test_the_graphql_door_needs_its_own_grant(self):
        _store_tokens(_entry(graphql_scopes=['*']))
        data = self._gql(self.ASK, {'m': 'Hello'})
        self.assertEqual(data['askJanus']['status'], 'refused')
        self.run_turn.assert_not_called()

    def test_janus_turn_reads_an_answer(self):
        turn = self._gql(self.ASK, {'m': 'Hello'})['askJanus']['turn']
        data = self._gql('query($t:String!){janusTurn(turn:$t){status reply}}', {'t': turn})
        self.assertEqual(data['janusTurn']['status'], 'done')

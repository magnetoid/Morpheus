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
        self.out_of_profile = _FakeTool('payouts.send', scopes=['payments.write'])
        self.public = _FakeTool('help.topics')
        self.tools = [self.read, self.write, self.out_of_profile, self.public]
        patcher = mock.patch(
            'plugins.installed.agent_mcp.linda_turn._all_tools', side_effect=lambda: self.tools
        )
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
        self.assertNotIn('payouts.send', names)

    def test_restricted_mode_narrows_the_catalogue(self):
        token = self._token(mode='sales')
        names = {t['name'] for t in self._post('tools/list', token=token).json()['result']['tools']}
        self.assertIn('stock.lookup', names)  # sales reads the store
        self.assertNotIn('settings.set', names)  # but changes nothing
        self.assertIn('help.topics', names)  # unscoped tools stay reachable
        resp = self._call('settings.set', {'sku': 'x'}, token=token)
        self.assertIn('not exposed', resp['error']['message'])
        self.assertEqual(self.write.calls, [])

    def test_linda_learns_through_janus_not_a_second_memory_store(self):
        remember = _FakeTool('memory.remember', scopes=['system.write'])
        self.tools.append(remember)
        names = {t['name'] for t in self._post('tools/list').json()['result']['tools']}
        resp = self._call('memory.remember', {'sku': 'x'})
        self.assertNotIn('memory.remember', names)
        self.assertIn('not exposed', resp['error']['message'])
        self.assertEqual(remember.calls, [])

    def test_out_of_profile_tool_is_refused_even_if_called_directly(self):
        resp = self._call('payouts.send', {'sku': 'A1'})
        self.assertIn('not exposed', resp['error']['message'])
        self.assertEqual(self.out_of_profile.calls, [])

    def test_platform_internals_and_shopper_tools_are_not_lindas(self):
        internals = _FakeTool('run_python', scopes=['system.read'])
        cart = _FakeTool('cart.add_item', scopes=['cart.write'])
        self.tools += [internals, cart]
        names = {t['name'] for t in self._post('tools/list').json()['result']['tools']}
        self.assertNotIn('run_python', names)
        self.assertNotIn('cart.add_item', names)
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        dev = self._post('tools/list', token=self._token(mode='dev')).json()['result']['tools']
        self.assertIn('run_python', {t['name'] for t in dev})

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

    def test_a_write_without_its_own_approval_flag_still_needs_a_yes(self):
        # Many Worker tools write without requires_approval; in a chat, whatever
        # Linda read could steer her into calling one.
        update = _FakeTool('catalog.update_product', scopes=['catalog.write'])
        self.tools.append(update)
        first = self._call('catalog.update_product', {'sku': 'NB-BLUE'})
        self.assertIn('approval_required', self._text(first)['error'])
        self.assertEqual(update.calls, [])
        self._say('yes')
        self.assertFalse(
            self._call('catalog.update_product', {'sku': 'NB-BLUE'})['result']['isError']
        )
        self.assertEqual(len(update.calls), 1)

    def test_spending_and_data_sharing_tools_need_a_yes(self):
        spawn = _FakeTool('delegate.spawn_workers', scopes=['system.write'])
        audience = _FakeTool('meta.sync_audience', scopes=['analytics.read'])
        self.tools += [spawn, audience]
        for name in ('delegate.spawn_workers', 'meta.sync_audience'):
            self.assertIn('approval_required', self._text(self._call(name, {'sku': 'x'}))['error'])
        self.assertEqual((spawn.calls, audience.calls), ([], []))

    def test_a_self_reporting_audit_runs_without_asking(self):
        audit = _FakeTool('seo.audit_product', scopes=['seo.write'])
        self.tools.append(audit)
        self.assertFalse(self._call('seo.audit_product', {'sku': 'x'})['result']['isError'])
        self.assertEqual(len(audit.calls), 1)

    def test_yes_then_a_retry_with_confirmed_spends_the_consent(self):
        # The model adds confirmed=True when it retries. That flag is its own
        # claim, not part of what the merchant approved.
        self._call('settings.set', {'sku': 'NB-BLUE'})
        self._say('yes please')
        retry = self._call('settings.set', {'sku': 'NB-BLUE', 'confirmed': True})
        self.assertFalse(retry['result']['isError'])
        self.assertEqual(len(self.write.calls), 1)

    def test_kill_switch_stops_every_write_linda_could_make(self):
        update = _FakeTool('catalog.update_product', scopes=['catalog.write'])
        self.tools.append(update)
        with mock.patch('core.agents.guardrails.agents_paused', return_value=True):
            resp = self._call('catalog.update_product', {'sku': 'x'})
        self.assertIn('paused', resp['error']['message'])

    def test_an_oversized_result_is_cut_with_a_hint(self):
        from plugins.installed.agent_mcp import linda_turn

        huge = _FakeTool('stock.dump', scopes=['system.read'])
        huge.invoke = lambda args, agent=None, context=None: types.SimpleNamespace(
            output={'rows': 'x' * (linda_turn.MAX_RESULT_CHARS * 2)}
        )
        self.tools.append(huge)
        text = self._call('stock.dump')['result']['content'][0]['text']
        self.assertLess(len(text), linda_turn.MAX_RESULT_CHARS + 200)
        self.assertIn('Narrow the call', text)

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


class LindaCatalogueTests(TestCase):
    """The real registry: Linda can reach the store work merchants ask for."""

    def _names(self, mode: str, *, superuser: bool = False) -> set[str]:
        from plugins.installed.agent_mcp.linda_turn import LindaTurn, catalogue

        user = types.SimpleNamespace(is_staff=True, is_superuser=superuser, pk=1)
        return {
            t.name for t in catalogue(LindaTurn(user=user, conversation_key=CONV, mode_slug=mode))
        }

    def test_general_mode_covers_everyday_store_work(self):
        names = self._names('general')
        for needed in (
            'orders.search',
            'orders.refund',
            'products.update_price',
            'inventory.low_stock_report',
            'inventory.adjust_stock',
            'seo.audit_product',
            'plugins.list',
            'analytics.summary',
            'customers.search',
            'catalog.update_product',
        ):
            self.assertIn(needed, names)
        for internal in ('run_python', 'db.list_models', 'platform.capabilities', 'cart.add_item'):
            self.assertNotIn(internal, names)

    def test_every_mode_has_tools_to_work_with(self):
        for mode in ('general', 'sales', 'support', 'ops'):
            self.assertGreater(len(self._names(mode)), 10, mode)
        self.assertIn('orders.search', self._names('sales'))
        self.assertIn('inventory.adjust_stock', self._names('ops'))

    def test_prompt_and_skills_name_only_tools_linda_has(self):
        # They once taught tools that did not exist (recent_orders, cache.clear)
        # or that Linda could not call, and she spent her steps looking for them.
        import re

        from core.assistant.janus_engine import bundled_skills_dir
        from core.assistant.prompts import LINDA_BASE_PROMPT

        names = self._names('general')
        texts = {'prompt': LINDA_BASE_PROMPT}
        texts.update(
            {str(p): p.read_text(encoding='utf-8') for p in bundled_skills_dir().rglob('SKILL.md')}
        )
        missing = set()
        for source, text in texts.items():
            for ref in re.findall(r'`([^`]+)`', text):
                if re.fullmatch(r'[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*', ref) and ref not in names:
                    missing.add((source.rsplit('/', 2)[-2] if '/' in source else source, ref))
        self.assertEqual(sorted(missing), [])

    def test_every_tool_declares_the_arguments_its_handler_requires(self):
        # A missing `required` lets a call through validation and crashes the
        # handler with a TypeError the model cannot learn from (plugins.describe).
        import inspect

        from plugins.installed.agent_mcp.linda_turn import _all_tools

        gaps = []
        for tool in _all_tools():
            params = inspect.signature(tool.handler).parameters.values()
            needed = {
                p.name
                for p in params
                if p.default is inspect.Parameter.empty
                and p.kind in (p.KEYWORD_ONLY, p.POSITIONAL_OR_KEYWORD)
                and p.name not in ('self', 'agent', 'context')
            }
            declared = set((tool.schema or {}).get('required') or [])
            if needed - declared:
                gaps.append((tool.name, sorted(needed - declared)))
        self.assertEqual(gaps, [])

    def test_settings_list_reads_the_stored_config(self):
        from core.assistant.tools.ecommerce import settings_list_tool
        from plugins.models import PluginConfig

        PluginConfig.objects.update_or_create(
            plugin_name='seo', defaults={'config': {'title': 'Shop', 'api_key': 'sk-12345678'}}
        )
        out = settings_list_tool.handler().output
        self.assertEqual(out['plugins']['seo']['config']['title'], 'Shop')
        self.assertNotIn('sk-12345678', json.dumps(out))


class LegacyEndpointTests(TestCase):
    def test_tools_list_survives_a_cache_outage(self):
        with mock.patch('django.core.cache.cache.incr', return_value=None):
            resp = Client().post(
                '/mcp/v1/', data=_rpc('tools/list'), content_type='application/json'
            )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('tools', resp.json()['result'])

    def test_external_clients_are_not_refused_by_csrf(self):
        # Claude Desktop / Cursor post JSON-RPC with no CSRF token.
        client = Client(enforce_csrf_checks=True)
        resp = client.post('/mcp/v1/', data=_rpc('tools/list'), content_type='application/json')
        self.assertNotEqual(resp.status_code, 403)

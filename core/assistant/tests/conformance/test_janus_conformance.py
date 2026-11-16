"""What Morpheus relies on from Janus, proven against the real Janus.

Everything else in the suite fakes Janus. Here the pinned ``janus`` runs as a
turn runs on a store: wired by the engine's own code (``janus_engine``), with a
stub model on loopback (``stub_model``) and the store's real MCP edge served by
a live test server. Each test drives ``Assistant().stream``, so the turn token,
the gate chain at the edge, the home Janus works in and the run record are the
production ones.

Skipped unless ``JANUS_CONFORMANCE_BIN`` names a Janus executable. With
``JANUS_CONFORMANCE_REPORT`` set, the suite also writes what the model was
offered (tool count and schema size, the baseline for deferred tool schemas).
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import LiveServerTestCase, override_settings

from core.agents.models import AgentRun
from core.assistant import janus_contract, janus_engine, janus_learning
from core.assistant.runtime import Assistant
from core.assistant.tests.conformance import stub_model
from plugins.testing import set_app_settings

JANUS = os.environ.get('JANUS_CONFORMANCE_BIN', '')
REPORT = os.environ.get('JANUS_CONFORMANCE_REPORT', '')
LOOPBACK = '127.0.0.1,localhost'
STORE_HOST = 'shop.conformance.test'


@unittest.skipUnless(JANUS, 'JANUS_CONFORMANCE_BIN names no Janus to test')
@override_settings(
    SECURE_SSL_REDIRECT=True, SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https')
)
class JanusConformanceTests(LiveServerTestCase):
    # A store's Janus reaches the edge as a turn does in production: loopback by
    # IP and port, naming the store's host and the https scheme in headers
    # (janus_engine._mcp_endpoint). Without them the edge answers 400 for the
    # host or 301 for the scheme, so every store tool listed proves both arrived.
    host = '127.0.0.1'
    report: dict = {}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.model = stub_model.StubModel().start()
        cls.addClassCleanup(cls.model.stop)
        cls.report = {}
        if REPORT:
            cls.addClassCleanup(cls._write_report)

    @classmethod
    def _write_report(cls):
        Path(REPORT).write_text(json.dumps(cls.report, indent=2, sort_keys=True), encoding='utf-8')

    def setUp(self):
        home = tempfile.mkdtemp(prefix='janus-conformance-')
        self.addCleanup(shutil.rmtree, home, True)
        override = self.settings(
            JANUS_BIN=JANUS, LINDA_MCP_URL='', LINDA_JANUS_HOME=home, ALLOWED_HOSTS=[STORE_HOST]
        )
        override.enable()
        self.addCleanup(override.disable)
        # Loopback never goes through a proxy the runner's environment names.
        env = mock.patch.dict(
            os.environ,
            {'NO_PROXY': LOOPBACK, 'no_proxy': LOOPBACK, 'PORT': str(self.server_thread.port)},
        )
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('LINDA_MCP_URL', None)  # put back by env.stop
        set_app_settings(
            self,
            'janus',
            model_source='custom',
            provider='openai',
            model='conformance-model',
            api_key='sk-conformance',
            base_url=self.model.base_url,
            web_search=False,
            turn_timeout_s=120,
        )
        self.user = get_user_model().objects.create_superuser(
            username='conformance', email='conformance@example.test', password='pw'
        )

    # ── helpers ──────────────────────────────────────────────────────────────

    def _key(self, chat: str) -> str:
        return f'user:{self.user.pk}:chat:{chat}'

    def _home(self, chat: str = 'a') -> Path:
        return janus_engine.linda_janus_home() / 'conv' / janus_engine._session_id(self._key(chat))

    def _turn(self, message: str, *answers: stub_model.Answer, chat: str = 'a') -> list[dict]:
        self.model.load(*answers)
        events = list(
            Assistant().stream(
                message=message, conversation_key=self._key(chat), context={'user': self.user}
            )
        )
        self.assertEqual(self.model.unexpected, 0, 'Janus called the model more than scripted')
        return events

    def _result(self, events: list[dict]):
        last = events[-1]
        self.assertIn(last['type'], ('final', 'error'))
        return last['type'], last['result']

    def _tool_results(self, request: dict) -> list[str]:
        return [str(m.get('content') or '') for m in request['messages'] if m.get('role') == 'tool']

    def _session(self, chat: str = 'a') -> dict:
        return json.loads((self._home(chat) / 'janus_session.json').read_text(encoding='utf-8'))

    # ── what the model is offered ────────────────────────────────────────────

    def test_the_model_is_offered_store_tools_and_reviewed_janus_tools_only(self):
        kind, result = self._result(self._turn('How is the shop?', stub_model.text('Fine.')))
        self.assertEqual((kind, result.text), ('final', 'Fine.'))

        first = self.model.requests[0]
        names = {t['function']['name'] for t in first.get('tools') or []}
        store = {n for n in names if n.startswith(stub_model.SERVER_PREFIX)}
        # -t loads these toolsets and nothing else: Janus's default set (terminal,
        # files, code, browser) would reach the web process's environment.
        reviewed = set().union(
            *(janus_contract.TOOLSETS.get(t, set()) for t in janus_engine.turn_toolsets())
        )
        self.assertEqual(names - store - reviewed, set())
        # The edge lists tools only for a valid turn token on the store's host over
        # https, so these prove the token and both headers reached it, and that
        # discovery finished before the first model call.
        self.assertIn(stub_model.store_tool('orders.search'), store)
        self.assertIn(stub_model.store_tool('cms.create_page'), store)

        system = str(first['messages'][0].get('content') or '')
        self.assertIn(janus_engine._SOUL.strip(), system)
        self.assertNotIn('You are Janus', system)
        home = self._home()
        self.assertTrue((home / '.no-bundled-skills').is_file())
        self.assertFalse((home / 'skills' / '.bundled_manifest').exists())

        type(self).report.update(
            {
                'janus': janus_engine.build_of([JANUS]),
                'tools_offered': len(names),
                'store_tools': len(store),
                'janus_tools': sorted(names - store),
                'tool_schema_bytes': len(json.dumps(first.get('tools') or [])),
                'model_paths_probed': sorted(set(self.model.other_paths)),
            }
        )

    # ── a turn through the store ─────────────────────────────────────────────

    def test_a_store_tool_call_goes_through_the_edge_and_back(self):
        events = self._turn(
            'Any orders?',
            stub_model.tool_call('orders.search', {}),
            stub_model.text('No orders yet.'),
        )
        kind, result = self._result(events)
        self.assertEqual((kind, result.text), ('final', 'No orders yet.'))

        # Janus hands the edge's answer back to the model, fenced as data: a
        # product text or a customer note in it is never read as instructions.
        self.assertEqual(len(self.model.requests), 2)
        answer = self._tool_results(self.model.requests[1])[-1]
        fence = f'<untrusted_tool_result source="{stub_model.store_tool("orders.search")}">'
        self.assertTrue(answer.startswith(fence), answer[:200])
        payload = json.loads(answer[answer.index('{') : answer.rindex('}') + 1])
        self.assertEqual(json.loads(payload['result'])['orders'], [])

        # The chat saw the call from the rows the edge records…
        started = [e for e in events if e['type'] == 'tool_call_started']
        finished = [e for e in events if e['type'] == 'tool_call_finished']
        self.assertEqual([e['name'] for e in started], ['orders.search'])
        self.assertEqual([e['name'] for e in finished], ['orders.search'])
        # …and the step from the progress hooks Janus ran.
        steps = [e for e in events if e['type'] == 'step']
        self.assertEqual([s['state'] for s in steps], ['running', 'done'])
        self.assertIsInstance(steps[-1]['ms'], int)

        # Usage comes from state.db: two calls of 100 in / 10 out.
        run = AgentRun.objects.get()
        self.assertEqual(run.state, 'completed')
        self.assertEqual((run.prompt_tokens, run.completion_tokens), (200, 20))
        self.assertEqual(run.tool_call_count, 1)
        self.assertEqual(run.metadata['api_calls'], 2)
        self.assertEqual(run.metadata['janus_commit'], janus_engine.build_of([JANUS])['commit'])

    def test_a_write_is_refused_until_the_merchant_says_yes(self):
        from plugins.installed.cms.models import Page

        events = self._turn(
            'Make an About page.',
            stub_model.tool_call('cms.create_page', {'title': 'About', 'body': '<p>Hi</p>'}),
            stub_model.text('Shall I create it?'),
        )
        self.assertEqual(self._result(events)[0], 'final')
        (answer,) = self._tool_results(self.model.requests[1])
        self.assertIn('approval_required', answer)
        self.assertFalse(Page.objects.filter(title='About').exists())

    # ── sessions ─────────────────────────────────────────────────────────────

    def test_a_conversation_resumes_and_a_lost_session_starts_fresh(self):
        started = time.time()
        self._turn('First.', stub_model.text('One.'))
        first = self._session()
        self.assertEqual(first['turns'], 1)
        # A timed-out turn's tokens are found through this lookup.
        self.assertEqual(janus_engine._session_started_since(self._home(), started), first['id'])

        self._turn('Second.', stub_model.text('Two.'))
        second = self._session()
        self.assertEqual((second['id'], second['turns']), (first['id'], 2))
        transcript = [m.get('content') for m in self.model.requests[0]['messages']]
        self.assertIn('One.', transcript)

        lost = {**self._session(), 'id': '20200101_000000_gone00'}
        (self._home() / 'janus_session.json').write_text(json.dumps(lost), encoding='utf-8')
        kind, result = self._result(self._turn('Third.', stub_model.text('Three.')))
        self.assertEqual((kind, result.text), ('final', 'Three.'))
        self.assertNotIn(self._session()['id'], (first['id'], lost['id']))

    # ── failures ─────────────────────────────────────────────────────────────

    def test_an_empty_reply_is_a_failed_turn(self):
        # Janus retries an empty reply three times before giving up.
        events = self._turn('Hello?', *[stub_model.empty() for _ in range(4)])
        self.assertEqual(len(self.model.requests), 4)
        kind, result = self._result(events)
        self.assertEqual(kind, 'error')
        self.assertNotIn('No reply', result.text)
        self.assertEqual(AgentRun.objects.get().state, 'failed')

    def test_a_model_error_is_a_failed_turn(self):
        events = self._turn('Hello?', stub_model.error(500))
        self.assertEqual(self._result(events)[0], 'error')
        self.assertEqual(AgentRun.objects.get().state, 'failed')
        # The status reaches the chat from the api_request_error hook; the
        # provider's text never does (it can quote a key).
        retries = [e for e in events if e['type'] == 'retry']
        self.assertEqual([e['status'] for e in retries], [500])

    # ── what Janus learns ────────────────────────────────────────────────────

    def test_notes_survive_the_turn_and_the_next_one_can_add_to_them(self):
        for note in ('The shop ships on Fridays.', 'Returns take 30 days.'):
            self._turn(
                'Remember this.',
                stub_model.tool_call(
                    'memory', {'action': 'add', 'target': 'memory', 'content': note}
                ),
                stub_model.text('Noted.'),
            )
            # The last tool result is this turn's: a resumed session carries the last.
            answer = self._tool_results(self.model.requests[1])[-1]
            # A hydrated MEMORY.md that did not round-trip reads to Janus as edited
            # by someone else, and it refuses every later write.
            self.assertNotIn('error', json.loads(answer))
        texts = [n['text'] for n in janus_learning.notes()['store']]
        self.assertEqual(texts, ['The shop ships on Fridays.', 'Returns take 30 days.'])

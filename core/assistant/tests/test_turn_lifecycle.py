"""A turn ends when Janus ends, and what it spent is counted once (findings J1, J3-J5).

A chat whose stream closed early (tab closed, reload, proxy drop) used to leave
Janus running with nobody to read its result: no reply, no usage, no run, no
harvest. Janus could outlive its deadline when the worker that started it was
recycled, spend was read from one session row (so a turn that died uncounted, or
the session a compression left behind, was never billed), two turns could run in
one home, and a store provider Janus has no name for ran on Janus's own choice.

No test here starts Janus: ``subprocess.run`` is faked, as in test_janus_engine.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
import subprocess
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import signals
from django.db import close_old_connections
from django.test import SimpleTestCase, TestCase, override_settings

import core.assistant.janus_engine as eng
from core.agents.models import AgentRun
from core.assistant import janus_learning as jl
from core.assistant import janus_sessions, runtime
from core.assistant.models import AssistantMessage, JanusLearning
from core.assistant.runtime import Assistant

JANUS = '/opt/janus/bin/janus'
_SESSIONS = (
    'CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, source TEXT, started_at REAL, '
    'parent_session_id TEXT, model TEXT, input_tokens INT, output_tokens INT, '
    'cache_read_tokens INT, cache_write_tokens INT, reasoning_tokens INT, '
    'api_call_count INT, estimated_cost_usd REAL)'
)


def _spend(home: Path, sid: str, input_tokens: int, output_tokens: int, parent: str | None = None):
    """Set one session's running totals in the home's state.db, as Janus does."""
    with contextlib.closing(sqlite3.connect(home / 'state.db')) as db, db:
        db.execute(_SESSIONS)
        db.execute(
            "INSERT OR REPLACE INTO sessions VALUES (?, 'cli', ?, ?, 'deepseek-v4-pro', "
            '?, ?, 0, 0, 0, 1, 0.01)',
            (sid, time.time(), parent, input_tokens, output_tokens),
        )


class _Proc:
    def __init__(self, *, stdout='ok', stderr='', returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _janus(*sessions, session='s1', stdout='ok', returncode=0, raises=None):
    """Stands in for `janus chat`: writes its sessions' totals, prints the reply."""

    def run(argv, **kwargs):
        home = Path(kwargs['env']['JANUS_HOME'])
        for row in sessions:
            _spend(home, *row)
        if raises is not None:
            raise raises
        return _Proc(stdout=stdout, stderr=f'session_id: {session}', returncode=returncode)

    return run


class _EngineCase(SimpleTestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.conv = self.home / 'conv' / eng._session_id('conv-1')
        for patcher in (
            mock.patch.object(eng, 'janus_cmd', return_value=[JANUS]),
            mock.patch.object(eng, 'linda_janus_home', return_value=self.home),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _turn(self, fake, **kwargs):
        with mock.patch.object(eng.subprocess, 'run', side_effect=fake) as spawn:
            out = eng.run_janus_turn(
                message='hi', conversation_key='conv-1', system_prompt='p', **kwargs
            )
        return out, spawn

    @staticmethod
    def _tokens(out):
        return out['usage']['input_tokens'], out['usage']['output_tokens']


class SpendFromTheHomeTests(_EngineCase):
    """A home is one conversation: all its sessions' totals are what it spent."""

    def test_a_turn_after_one_that_was_never_counted_bills_both(self):
        out, _ = self._turn(_janus(('s1', 1000, 50)))
        self.assertEqual(self._tokens(out), (1000, 50))
        # A turn whose process died before it could report (the worker was
        # recycled): Janus spent, nothing was counted.
        _spend(self.conv, 's1', 2600, 90)
        out, _ = self._turn(_janus(('s1', 3000, 100)))
        self.assertEqual(self._tokens(out), (2000, 50))
        self.assertEqual(out['usage']['model'], 'deepseek-v4-pro')

    def test_a_compressed_turn_bills_the_old_session_and_its_continuation(self):
        self._turn(_janus(('s1', 1000, 50)))
        # Janus compressed mid-turn: it spent on s1, ended it, carried on in s2.
        out, _ = self._turn(_janus(('s1', 1800, 70), ('s2', 300, 20, 's1'), session='s2'))
        self.assertEqual(self._tokens(out), (1100, 40))
        self.assertEqual(eng._stored_session_id(self.conv), 's2')

    def test_a_timeout_after_compression_bills_both_sessions(self):
        self._turn(_janus(('s1', 1000, 50)))
        killed = _janus(
            ('s1', 1500, 60), ('s2', 400, 10, 's1'), raises=subprocess.TimeoutExpired(JANUS, 240)
        )
        out, _ = self._turn(killed)
        self.assertIn('timed out', out['error'])
        self.assertEqual(self._tokens(out), (900, 20))

    def test_the_first_turn_on_an_older_home_bills_only_itself(self):
        # A conversation from before homes kept a figure: its history was
        # billed turn by turn already.
        self.conv.mkdir(parents=True)
        _spend(self.conv, 's1', 5000, 200)
        (self.conv / 'janus_session.json').write_text(
            json.dumps({'id': 's1', 'turns': 3, 'last_at': time.time()}), encoding='utf-8'
        )
        out, _ = self._turn(_janus(('s1', 5600, 230)))
        self.assertEqual(self._tokens(out), (600, 30))
        out, _ = self._turn(_janus(('s1', 6000, 240)))
        self.assertEqual(self._tokens(out), (400, 10))

    def _prune(self, home: Path = None):
        with contextlib.closing(sqlite3.connect((home or self.conv) / 'state.db')) as db, db:
            db.execute('DELETE FROM sessions')

    def test_sessions_pruned_between_turns_bill_only_the_new_turn(self):
        self._turn(_janus(('s1', 1000, 50)))
        self._prune()  # the total is now below what was counted
        out, _ = self._turn(_janus(('s2', 300, 20), session='s2'))
        self.assertEqual(self._tokens(out), (300, 20))
        out, _ = self._turn(_janus(('s2', 500, 30), session='s2'))
        self.assertEqual(self._tokens(out), (200, 10))

    def test_sessions_pruned_mid_turn_never_bill_a_negative(self):
        self._turn(_janus(('s1', 1000, 50)))

        def prunes_then_works(argv, **kwargs):
            self._prune(Path(kwargs['env']['JANUS_HOME']))
            return _janus(('s2', 300, 20), session='s2')(argv, **kwargs)

        out, _ = self._turn(prunes_then_works)
        self.assertEqual(self._tokens(out), (0, 0))
        # The figure starts again from what the home holds now.
        out, _ = self._turn(_janus(('s2', 450, 25), session='s2'))
        self.assertEqual(self._tokens(out), (150, 5))

    def test_a_state_db_that_cannot_be_read_never_bills_the_history_again(self):
        self._turn(_janus(('s1', 1000, 50)))
        real, reads = eng._home_usage, []

        def unreadable_once(*args):
            reads.append(args)
            return {} if len(reads) == 1 else real(*args)

        with mock.patch.object(janus_sessions, '_home_usage', side_effect=unreadable_once):
            out, _ = self._turn(_janus(('s1', 1400, 60)))
        self.assertEqual(self._tokens(out), (400, 10))

    def test_a_lost_session_keeps_what_was_counted(self):
        self._turn(_janus(('s1', 1000, 50)))
        fresh = _janus(('s2', 200, 10), session='s2')

        def lost_then_fresh(argv, **kwargs):
            if '--resume' in argv:
                return _Proc(stdout='', stderr='Session not found: s1', returncode=1)
            return fresh(argv, **kwargs)

        out, spawn = self._turn(lost_then_fresh)
        self.assertEqual(spawn.call_count, 2)
        self.assertEqual(out['error'], '')
        self.assertEqual(self._tokens(out), (200, 10))


class DeadlineTests(_EngineCase):
    """``subprocess.run(timeout=…)`` holds only while the parent lives. coreutils
    ``timeout`` (in the image; not on macOS) stops Janus whoever is still around."""

    def _wrapped(self, fake, wrapper='/usr/bin/timeout'):
        with mock.patch.object(eng, '_timeout_bin', return_value=wrapper):
            return self._turn(fake, timeout_s=30)

    def test_janus_runs_under_coreutils_timeout_where_the_host_has_it(self):
        _, spawn = self._wrapped(_janus())
        argv = spawn.call_args.args[0]
        self.assertEqual(argv[:3], ['/usr/bin/timeout', '-k', '5'])
        self.assertLessEqual(int(argv[3]), 30)
        self.assertEqual(argv[4:6], [JANUS, 'chat'])
        # The wrapper must be the one that stops Janus: Python killing the wrapper
        # first would leave Janus running with nothing to stop it.
        self.assertGreater(spawn.call_args.kwargs['timeout'], int(argv[3]) + 5)

    def test_without_it_janus_is_started_directly(self):
        _, spawn = self._wrapped(_janus(), wrapper='')
        self.assertEqual(spawn.call_args.args[0][:2], [JANUS, 'chat'])
        self.assertLessEqual(spawn.call_args.kwargs['timeout'], 30)

    def test_the_wrapper_stopping_janus_is_a_timeout(self):
        out, _ = self._wrapped(_janus(('s1', 900, 40), stdout='half an ans', returncode=124))
        self.assertEqual(out['error'], 'janus timed out after 30s')
        self.assertEqual(out['text'], '')
        self.assertEqual(self._tokens(out), (900, 40))
        self.assertIn('took longer', runtime._friendly_provider_error(out['error']))

    def test_exit_124_without_the_wrapper_is_janus_own_failure(self):
        out, _ = self._wrapped(_janus(returncode=124), wrapper='')
        self.assertNotIn('timed out', out['error'])
        self.assertTrue(out['error'])

    def test_a_janus_the_wrapper_cannot_start_is_a_spawn_failure(self):
        # Without the wrapper a missing binary raises; with it the wrapper exits
        # 127 and says "timeout: failed to run command", which must not read to
        # the merchant as a provider timing out.
        missing = _Proc(
            stdout='',
            stderr=f"timeout: failed to run command '{JANUS}': No such file",
            returncode=127,
        )
        out, _ = self._wrapped(mock.Mock(return_value=missing))
        self.assertEqual(out['error'], 'janus spawn failed: exit 127')
        self.assertIn('AI provider error', runtime._friendly_provider_error(out['error']))

    def test_a_kill_is_a_timeout_only_at_the_deadline(self):
        # After its TERM the wrapper exits 124. Its KILL goes to the whole process
        # group, itself included, so Python then sees signal 9 (a shell says 137).
        self.assertTrue(eng._stopped_at_deadline(124, 3.0, 30))
        self.assertTrue(eng._stopped_at_deadline(-9, 35.2, 30))
        self.assertTrue(eng._stopped_at_deadline(137, 35.2, 30))
        # Killed early is something else (out of memory), and so is a plain failure.
        self.assertFalse(eng._stopped_at_deadline(-9, 3.0, 30))
        self.assertFalse(eng._stopped_at_deadline(1, 35.2, 30))


class OneTurnPerHomeTests(_EngineCase):
    """A second turn's hydrate would rewrite the notes and remove the files the
    first turn's Janus wrote and has not harvested yet."""

    def _slow(self):
        started, release = threading.Event(), threading.Event()

        def settle():
            # Let Janus's thread finish before the home is removed under it.
            release.set()
            for thread in threading.enumerate():
                if thread.name == 'janus-turn':
                    thread.join(10)

        self.addCleanup(settle)

        def slow(argv, **kwargs):
            started.set()
            release.wait(10)
            return _Proc(stdout='first')

        return slow, started, release

    def _open(self):
        return eng.iter_janus_turn(
            message='hi', conversation_key='conv-1', system_prompt='p', tick_s=0.02
        )

    def test_a_second_turn_is_refused_while_the_first_is_running(self):
        slow, started, release = self._slow()
        with mock.patch.object(eng.subprocess, 'run', side_effect=slow) as spawn:
            first = self._open()
            self.assertIsNone(next(first))
            self.assertTrue(started.wait(10))
            second = eng.run_janus_turn(
                message='again', conversation_key='conv-1', system_prompt='p'
            )
            self.assertEqual(second['error'], 'janus is busy with this conversation')
            self.assertEqual(second['text'], '')
            # No second Janus, so no model call.
            self.assertEqual(spawn.call_count, 1)
            # Another conversation is not held up.
            other = eng.iter_janus_turn(
                message='hi', conversation_key='conv-2', system_prompt='p', tick_s=0.02
            )
            self.assertIsNone(next(other))
            release.set()
            done = [item for item in first if item][-1]
            list(other)
        self.assertEqual(done['text'], 'first')
        out, _ = self._turn(_janus(stdout='next'))
        self.assertEqual(out['text'], 'next')

    def test_a_failed_turn_frees_the_conversation(self):
        out, _ = self._turn(OSError('exec format error'))
        self.assertIn('spawn failed', out['error'])
        with (
            mock.patch.object(eng, '_ensure_config', side_effect=OSError('disk full')),
            self.assertRaises(OSError),
        ):
            self._turn(_janus())
        out, _ = self._turn(_janus(stdout='works again'))
        self.assertEqual(out['text'], 'works again')

    def test_a_turn_its_caller_closed_frees_the_conversation(self):
        slow, started, _release = self._slow()
        with mock.patch.object(eng.subprocess, 'run', side_effect=slow):
            turn = self._open()
            next(turn)
            self.assertTrue(started.wait(10))
            self.assertIsNone(eng._lock_home(self.conv))
            turn.close()
            held = eng._lock_home(self.conv)
        self.assertIsNotNone(held)
        held.close()

    def test_the_merchant_is_told_linda_is_still_working(self):
        self.assertEqual(
            runtime._friendly_provider_error('janus is busy with this conversation'),
            'Linda is still working on your last message. Try again in a moment.',
        )


class UnsupportedProviderTests(_EngineCase):
    """Without a provider Janus picks one itself (``auto``), from whatever keys the
    container holds: a model the store did not choose and may not have priced."""

    def setUp(self):
        super().setUp()
        from core.agents.provider_registry import ProviderConfig

        conf = ProviderConfig(
            provider='openrouter',
            api_key='sk-test',
            base_url='',
            model='anthropic/claude-3.5-sonnet',
            embedding_model='',
        )
        registry = 'core.agents.provider_registry'
        for patcher in (
            mock.patch(f'{registry}.get_active_provider_name', return_value='openrouter'),
            mock.patch(f'{registry}.get_provider_config', return_value=conf),
            mock.patch.object(eng.janus_settings, 'custom_provider', return_value=None),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_a_turn_never_runs_on_a_provider_janus_picks_itself(self):
        out, spawn = self._turn(_janus())
        self.assertEqual(out['error'], 'janus cannot run on openrouter')
        self.assertEqual(out['text'], '')
        spawn.assert_not_called()

    def test_the_merchant_is_told_where_to_choose_a_provider(self):
        self.assertEqual(
            runtime._friendly_provider_error('janus cannot run on openrouter'),
            'Linda cannot run on openrouter. Choose a provider for her under '
            'Settings → AI → Janus.',
        )

    def test_naming_the_turns_provider_never_raises(self):
        # The turn token and the run record name the provider before the engine runs.
        self.assertEqual(Assistant._turn_provider({}), ('', ''))


class BackgroundTests(SimpleTestCase):
    """Outside tests the rest of a turn runs on a thread of its own. (Under tests it
    runs inline: a second thread that touches the database locks the test database.)"""

    @override_settings(_RUNNING_TESTS=False)
    def test_a_turn_handed_over_is_finished_on_its_own_thread(self):
        ran_on, done = [], threading.Event()

        def turn():
            yield 'progress'
            ran_on.append(threading.current_thread().name)
            yield 'final'
            done.set()

        suspended = turn()
        next(suspended)  # the request thread read this far, then its reader left
        runtime._finish_unwatched(suspended, 't:handed-over')
        self.assertTrue(done.wait(10))
        self.assertEqual(ran_on, ['linda-turn'])


@contextlib.contextmanager
def _as_the_server_closes_it():
    """``response.close()`` the way Django's test client calls it: the signal's
    connection clean-up would close the test's own transaction."""
    signals.request_finished.disconnect(close_old_connections)
    try:
        yield
    finally:
        signals.request_finished.connect(close_old_connections)


class UnwatchedTurnTests(TestCase):
    """The browser going away closes the response generator. The turn goes on."""

    KEY = 't:unwatched'

    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.user = get_user_model().objects.create_user(
            username='ana', email='a@x.com', password='x', is_staff=True
        )
        home = override_settings(LINDA_JANUS_HOME=tmp.name)
        home.enable()
        self.addCleanup(home.disable)
        for patcher in (
            mock.patch.object(eng, 'janus_cmd', return_value=[JANUS]),
            mock.patch.object(eng.subprocess, 'run', side_effect=self._janus),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    @staticmethod
    def _janus(argv, **kwargs):
        home = Path(kwargs['env']['JANUS_HOME'])
        _spend(home, 's1', 1000, 50)
        (home / 'memories').mkdir(exist_ok=True)
        (home / jl.MEMORY_FILE).write_text('Ships on Fridays', encoding='utf-8')
        return _Proc(stdout='Three orders are waiting.', stderr='session_id: s1')

    def _stream(self):
        return Assistant().stream(
            message='hi', conversation_key=self.KEY, context={'user': self.user}
        )

    def _assert_finished(self, key=KEY):
        reply = AssistantMessage.objects.get(conversation__key=key, role='assistant')
        self.assertEqual(reply.content, 'Three orders are waiting.')
        self.assertEqual(
            (reply.prompt_tokens, reply.completion_tokens, reply.model),
            (1000, 50, 'deepseek-v4-pro'),
        )
        self.assertEqual(JanusLearning.objects.get(path=jl.MEMORY_FILE).content, 'Ships on Fridays')
        self.assertEqual(AgentRun.objects.get(agent_name='linda').state, 'completed')

    def test_a_turn_whose_reader_left_is_finished_anyway(self):
        stream = self._stream()
        self.assertEqual(next(stream)['type'], 'progress')
        stream.close()  # the tab was closed
        self._assert_finished()

    def test_the_rest_of_the_turn_runs_off_the_request(self):
        handed = []
        with mock.patch.object(runtime, '_in_background', side_effect=handed.append):
            stream = self._stream()
            next(stream)
            stream.close()
        self.assertFalse(AssistantMessage.objects.filter(role='assistant').exists())
        handed.pop()()  # later, on its own thread
        self._assert_finished()

    def test_closing_the_http_response_finishes_the_turn(self):
        self.client.force_login(self.user)
        response = self.client.post(
            '/dashboard/assistant/stream/',
            data=json.dumps({'message': 'hi'}),
            content_type='application/json',
        )
        self.assertIn(b'"progress"', next(iter(response.streaming_content)))
        with _as_the_server_closes_it():
            response.close()  # what the server does once the browser has gone
        self._assert_finished(key=f'user:{self.user.pk}')

    def test_a_failure_after_the_reader_left_is_logged_not_raised(self):
        with (
            mock.patch.object(eng, 'iter_janus_turn', side_effect=RuntimeError('boom')),
            self.assertLogs('morpheus.assistant', level='ERROR') as logs,
        ):
            stream = self._stream()
            next(stream)
            stream.close()
        self.assertIn('boom', '\n'.join(logs.output))

    def test_a_turn_read_to_the_end_is_stored_once(self):
        events = list(self._stream())
        self.assertEqual(events[-1]['type'], 'final')
        self._assert_finished()

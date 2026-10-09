"""Janus engine adapter for Linda — no live Janus process in the suite.

`morph/settings.py` points ``JANUS_BIN`` at a missing path under tests, so an
unmocked turn is a reported spawn failure, never a model call. Tests that need a
turn mock ``subprocess.run`` or ``run_janus_turn``.
"""

from __future__ import annotations

import subprocess
import types
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.test import SimpleTestCase, override_settings

import core.assistant.janus_engine as eng
from core.assistant.janus_engine import (
    _child_env,
    _ensure_config,
    bundled_skill_names,
    bundled_skills_dir,
    janus_available,
    run_janus_turn,
    turn_timeout_s,
)


def _staff(**kw):
    return types.SimpleNamespace(
        is_staff=kw.get('is_staff', True),
        is_superuser=kw.get('is_superuser', False),
        pk=1,
    )


class JanusDiscoveryTests(SimpleTestCase):
    def test_missing_binary_is_unavailable(self):
        # `janus` may genuinely be on this machine's PATH, so neutralise the
        # PATH lookup too — otherwise the assertion is environment-dependent
        # and the test degrades into asserting nothing.
        with (
            override_settings(JANUS_BIN='', JANUS_ENGINE_ROOT='/no/such/janus'),
            mock.patch.object(eng.shutil, 'which', return_value=None),
            mock.patch.object(eng, 'engine_root', return_value=None),
        ):
            self.assertFalse(janus_available())

    def test_explicit_bin_wins(self):
        with override_settings(JANUS_BIN='/opt/janus/bin/janus'):
            self.assertEqual(eng.janus_cmd(), ['/opt/janus/bin/janus'])


class McpEndpointTests(SimpleTestCase):
    """How the subprocess reaches the store's MCP server.

    Measured on prod: plain http loopback gets a 301 to https, which drops the
    JSON-RPC body; loopback naming the real host and https scheme answers in
    0.03s; the public URL answers in 0.25s after a round trip through Cloudflare.
    """

    @override_settings(LINDA_MCP_URL='https://shop.example/mcp/admin/v1')
    def test_explicit_url_gets_exactly_one_slash_and_no_extra_headers(self):
        self.assertEqual(eng._mcp_endpoint(None), ('https://shop.example/mcp/admin/v1/', {}))

    @override_settings(LINDA_MCP_URL='https://shop.example/mcp/admin/v1/')
    def test_explicit_url_slash_is_preserved(self):
        self.assertEqual(eng._mcp_endpoint(None)[0], 'https://shop.example/mcp/admin/v1/')

    @override_settings(LINDA_MCP_URL='')
    def test_request_host_and_scheme_ride_on_loopback(self):
        request = types.SimpleNamespace(get_host=lambda: 'shop.example', is_secure=lambda: True)
        with mock.patch.dict(eng.os.environ, {'PORT': '9001'}, clear=False):
            url, headers = eng._mcp_endpoint({'request': request})
        self.assertEqual(url, 'http://127.0.0.1:9001/mcp/admin/v1/')
        self.assertEqual(headers, {'Host': 'shop.example', 'X-Forwarded-Proto': 'https'})

    @override_settings(
        LINDA_MCP_URL='',
        ALLOWED_HOSTS=['.internal', 'localhost', 'shop.example'],
        SECURE_SSL_REDIRECT=True,
    )
    def test_without_a_request_the_configured_host_is_used(self):
        _, headers = eng._mcp_endpoint(None)
        self.assertEqual(headers, {'Host': 'shop.example', 'X-Forwarded-Proto': 'https'})

    @override_settings(LINDA_MCP_URL='', ALLOWED_HOSTS=['localhost'], SECURE_SSL_REDIRECT=False)
    def test_local_dev_needs_no_extra_headers(self):
        self.assertEqual(eng._mcp_endpoint(None)[1], {})

    def test_headers_are_written_as_quoted_yaml(self):
        body = eng._config_text('http://127.0.0.1:8000/mcp/admin/v1/', {'Host': 'shop.example'})
        self.assertIn('      Host: "shop.example"', body)


class ConfigTests(SimpleTestCase):
    """The per-conversation config Janus reads. It must never hold a credential."""

    def test_no_credential_is_written_to_disk(self):
        # The MCP header references the per-turn token in the environment, so a
        # conversation home on disk (or on a volume, later) holds nothing reusable.
        with TemporaryDirectory() as tmp:
            body = _ensure_config(Path(tmp), mcp_url='https://s/mcp/').read_text(encoding='utf-8')
        self.assertIn('Authorization: "Bearer ${LINDA_TURN_TOKEN}"', body)
        self.assertNotIn('lt1.', body)

    def test_changed_url_is_rewritten(self):
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _ensure_config(home, mcp_url='https://old.example/mcp/')
            _ensure_config(home, mcp_url='https://new.example/mcp/')
            body = (home / 'config.yaml').read_text(encoding='utf-8')
        self.assertIn('new.example', body)
        self.assertNotIn('old.example', body)

    def test_unchanged_config_is_left_alone(self):
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg = _ensure_config(home, mcp_url='https://s/mcp/')
            first = cfg.read_text(encoding='utf-8')
            cfg2 = _ensure_config(home, mcp_url='https://s/mcp/')
            self.assertEqual(first, cfg2.read_text(encoding='utf-8'))
            self.assertEqual(cfg.stat().st_mode & 0o777, 0o600)

    def test_terminal_scanner_is_off(self):
        # tirith only scans terminal commands, which a turn cannot run. Left on,
        # it printed a warning into the merchant's first reply (live, v0.63.1)
        # and started a binary download on every turn.
        body = eng._config_text('https://s/mcp/')
        self.assertIn('security:\n  tirith_enabled: false', body)

    def test_config_reports_each_step_to_the_conversation_home(self):
        with TemporaryDirectory() as tmp:
            body = _ensure_config(Path(tmp), mcp_url='https://s/mcp/').read_text(encoding='utf-8')
            self.assertIn(str(Path(tmp) / 'progress.jsonl'), body)
        self.assertIn('hooks_auto_accept: true', body)
        self.assertIn('  pre_tool_call:', body)
        self.assertIn('janus_progress_hook.py', body)

    def test_config_points_at_bundled_ecommerce_skills(self):
        with TemporaryDirectory() as tmp:
            cfg = _ensure_config(Path(tmp), mcp_url='https://s/mcp/')
            body = cfg.read_text(encoding='utf-8')
        skills = bundled_skills_dir()
        self.assertTrue(skills.is_dir(), f'missing bundled skills at {skills}')
        self.assertIn('external_dirs', body)
        self.assertIn(str(skills).replace('\\', '/'), body)
        self.assertIn('morpheus_admin', body)


class JanusHomeTests(SimpleTestCase):
    """v0.63.0 put homes under BASE_DIR. In the image /app is root-owned, so every
    real turn raised PermissionError until v0.64.1 — invisible to tests that
    patched the home to a temp dir."""

    @override_settings(LINDA_JANUS_HOME='')
    def test_default_home_is_private_and_outside_the_app_tree(self):
        from django.conf import settings

        with (
            TemporaryDirectory() as tmp,
            mock.patch.object(eng.tempfile, 'gettempdir', return_value=tmp),
        ):
            home = eng.linda_janus_home()
            self.assertEqual(home, Path(tmp) / 'linda-janus')
            self.assertEqual(home.stat().st_mode & 0o777, 0o700)
        self.assertFalse(str(home).startswith(str(settings.BASE_DIR)))

    def test_configured_home_is_used(self):
        with TemporaryDirectory() as tmp, override_settings(LINDA_JANUS_HOME=f'{tmp}/volume'):
            self.assertEqual(eng.linda_janus_home(), Path(tmp) / 'volume')

    def test_unwritable_home_is_a_reported_failure_not_a_crash(self):
        with (
            mock.patch.object(eng, 'janus_cmd', return_value=['/opt/janus/bin/janus']),
            mock.patch.object(
                eng, 'linda_janus_home', side_effect=PermissionError('/app/.linda-janus')
            ),
        ):
            out = run_janus_turn(message='hi', conversation_key='c', system_prompt='p')
        self.assertIn('janus home unavailable', out['error'])
        self.assertEqual(out['text'], '')


class ChildEnvTests(SimpleTestCase):
    """The subprocess runs its own tool loop; it gets an allowlist, never the
    parent's environment."""

    def test_platform_secrets_are_withheld(self):
        fake = {
            'PATH': '/usr/bin',
            'DATABASE_URL': 'postgres://user:pw@db/morph',
            'SECRET_KEY': 'django-secret',
            'STRIPE_SECRET_KEY': 'sk_live_x',
            'AWS_SECRET_ACCESS_KEY': 'aws',
            'OPENAI_API_KEY': 'sk-openai',
        }
        with mock.patch.dict(eng.os.environ, fake, clear=True):
            env = _child_env({})
        self.assertEqual(env['PATH'], '/usr/bin')
        self.assertEqual(env['OPENAI_API_KEY'], 'sk-openai')
        for leaked in ('DATABASE_URL', 'SECRET_KEY', 'STRIPE_SECRET_KEY', 'AWS_SECRET_ACCESS_KEY'):
            self.assertNotIn(leaked, env)

    def test_reserved_janus_vars_are_not_inherited(self):
        with mock.patch.dict(
            eng.os.environ,
            {'PATH': '/usr/bin', 'JANUS_YOLO_MODE': '1', 'JANUS_MODEL': 'x'},
            clear=True,
        ):
            env = _child_env({'JANUS_YOLO_MODE': '0'})
        self.assertEqual(env['JANUS_YOLO_MODE'], '0')
        self.assertEqual(env['JANUS_MODEL'], 'x')


class _FakeProc:
    def __init__(self, *, stdout='', stderr='', returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class TurnTests(SimpleTestCase):
    def _run(self, proc, **kw):
        with (
            TemporaryDirectory() as tmp,
            mock.patch.object(eng, 'janus_cmd', return_value=['/bin/true']),
            mock.patch.object(eng, 'linda_janus_home', return_value=Path(tmp)),
            mock.patch.object(eng, 'engine_root', return_value=None),
            mock.patch.object(eng.subprocess, 'run', return_value=proc) as spawn,
        ):
            out = run_janus_turn(
                message='hi',
                conversation_key='t',
                system_prompt='You are Linda.',
                **kw,
            )
        return out, spawn

    def test_unavailable_returns_error_payload(self):
        with mock.patch.object(eng, 'janus_cmd', return_value=None):
            out = run_janus_turn(message='hi', conversation_key='t', system_prompt='You are Linda.')
        self.assertEqual(out['error'], 'janus_unavailable')
        self.assertEqual(out['text'], '')

    def test_auto_approve_is_off_by_default(self):
        _, spawn = self._run(_FakeProc(stdout='ok'))
        self.assertEqual(spawn.call_args.kwargs['env']['JANUS_YOLO_MODE'], '0')

    @override_settings(LINDA_JANUS_AUTO_APPROVE=True)
    def test_auto_approve_is_opt_in(self):
        _, spawn = self._run(_FakeProc(stdout='ok'))
        self.assertEqual(spawn.call_args.kwargs['env']['JANUS_YOLO_MODE'], '1')

    def test_crash_after_partial_output_is_an_error(self):
        out, _ = self._run(
            _FakeProc(stdout='Here is the first half of my ans', stderr='boom', returncode=1)
        )
        self.assertEqual(out['text'], '')
        self.assertIn('boom', out['error'])
        self.assertIn('partial output', out['error'])

    def test_long_json_envelope_is_unwrapped(self):
        answer = 'x' * 900
        payload = '{"padding": "%s", "final_response": "done"}' % ('p' * 400)
        out, _ = self._run(_FakeProc(stdout=payload))
        self.assertEqual(out['text'], 'done')
        self.assertNotIn('padding', out['text'])
        self.assertNotIn(answer, out['text'])

    def test_plain_text_passes_through(self):
        out, _ = self._run(_FakeProc(stdout='  Two copies are in stock.  '))
        self.assertEqual(out['text'], 'Two copies are in stock.')
        self.assertEqual(out['error'], '')

    def test_timeout_is_reported_not_raised(self):
        with (
            TemporaryDirectory() as tmp,
            mock.patch.object(eng, 'janus_cmd', return_value=['/bin/true']),
            mock.patch.object(eng, 'linda_janus_home', return_value=Path(tmp)),
            mock.patch.object(
                eng.subprocess,
                'run',
                side_effect=subprocess.TimeoutExpired(cmd='janus', timeout=55),
            ),
        ):
            out = run_janus_turn(message='hi', conversation_key='t', system_prompt='p')
        self.assertIn('timed out', out['error'])
        self.assertEqual(out['text'], '')

    def test_default_timeout_stays_within_the_cap(self):
        from core.assistant import janus_settings

        self.assertLessEqual(turn_timeout_s(), janus_settings.MAX_TURN_TIMEOUT_S)


class TurnInvocationTests(SimpleTestCase):
    """How a turn is launched. Each of these shipped broken in v0.63.0."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)

    def _turn(self, *procs):
        with (
            mock.patch.object(eng, 'janus_cmd', return_value=['/opt/janus/bin/janus']),
            mock.patch.object(eng, 'linda_janus_home', return_value=self.home),
            mock.patch.object(eng, 'engine_root', return_value=None),
            mock.patch.object(eng.subprocess, 'run', side_effect=list(procs)) as spawn,
        ):
            out = run_janus_turn(message='hi', conversation_key='conv-1', system_prompt='p')
        return out, [c.args[0] for c in spawn.call_args_list]

    def test_default_toolset_never_loads(self):
        # Without -t, `janus chat` loads 56 tools including terminal,
        # write_file and execute_code, running as the user that owns /app.
        _, calls = self._turn(_FakeProc(stdout='ok'))
        argv = calls[0]
        self.assertIn('-t', argv)
        toolsets = argv[argv.index('-t') + 1].split(',')
        self.assertEqual(toolsets, list(eng.turn_toolsets()))
        # An allowlist, so a new toolset is a decision made here, with a reason.
        self.assertLessEqual(
            set(toolsets),
            {eng.MCP_SERVER_NAME, 'skills', 'memory', 'todo', 'session_search', 'search'},
        )
        for forbidden in (
            'terminal',
            'file',
            'code_execution',
            'browser',
            'janus-cli',
            # web_extract and vision fetch a URL the model chooses: an outbound
            # channel for anything she has read.
            'web',
            'vision',
            # delegate_task runs a model-supplied acp_command (subprocess.Popen).
            'delegation',
            'messaging',
            'cronjob',
            'tool_synthesis',
            'computer_use',
        ):
            self.assertNotIn(forbidden, toolsets)

    def test_toolset_names_the_configured_mcp_server(self):
        self.assertEqual(eng.TURN_TOOLSETS[0], eng.MCP_SERVER_NAME)
        self.assertIn(f'  {eng.MCP_SERVER_NAME}:', eng._config_text('https://s/mcp/'))

    def test_runs_in_the_conversation_home_not_the_engine_checkout(self):
        with (
            mock.patch.object(eng, 'janus_cmd', return_value=['/opt/janus/bin/janus']),
            mock.patch.object(eng, 'linda_janus_home', return_value=self.home),
            mock.patch.object(eng, 'engine_root', return_value=Path('/src/janus-agent')),
            mock.patch.object(eng.subprocess, 'run', return_value=_FakeProc(stdout='ok')) as spawn,
        ):
            run_janus_turn(message='hi', conversation_key='conv-1', system_prompt='p')
        cwd = spawn.call_args.kwargs['cwd']
        self.assertTrue(cwd.startswith(str(self.home)))
        self.assertNotIn('janus-agent', cwd)

    def test_home_env_points_at_the_conversation_home(self):
        # The inherited HOME (/app in the image) is not writable.
        with (
            mock.patch.object(eng, 'janus_cmd', return_value=['/opt/janus/bin/janus']),
            mock.patch.object(eng, 'linda_janus_home', return_value=self.home),
            mock.patch.object(eng.subprocess, 'run', return_value=_FakeProc(stdout='ok')) as spawn,
        ):
            run_janus_turn(message='hi', conversation_key='conv-1', system_prompt='p')
        env = spawn.call_args.kwargs['env']
        self.assertEqual(env['HOME'], env['JANUS_HOME'])
        self.assertTrue(env['HOME'].startswith(str(self.home)))

    def test_tool_iterations_fit_the_turn_timeout(self):
        from core.assistant import janus_settings

        self.assertIn(f'max_turns: {eng.MAX_TOOL_TURNS}', eng._config_text('https://s/mcp/'))
        # Room for real work (the owner found 10 steps in 120s constraining),
        # and the steps still fit the time: ~7s each measured on prod.
        self.assertEqual((eng.MAX_TOOL_TURNS, eng._DEFAULT_TIMEOUT_S), (30, 240))
        self.assertLessEqual(eng.MAX_TOOL_TURNS * 7, eng._DEFAULT_TIMEOUT_S)
        self.assertEqual(
            (janus_settings.MAX_TOOL_TURNS, janus_settings.MAX_TURN_TIMEOUT_S), (60, 300)
        )

    def test_quiet_mode_is_used(self):
        _, calls = self._turn(_FakeProc(stdout='ok'))
        self.assertIn('-Q', calls[0])

    def test_follow_up_resumes_by_session_id_not_continue(self):
        # A bare --continue looks for the newest `cli` session, never `linda`,
        # so every second message in a conversation exited 1.
        sid = '20260913_010203_abc123'
        self._turn(_FakeProc(stdout='first', stderr=f'\nsession_id: {sid}\n'))
        out, calls = self._turn(_FakeProc(stdout='second', stderr=f'\nsession_id: {sid}\n'))
        argv = calls[0]
        self.assertNotIn('--continue', argv)
        self.assertEqual(argv[argv.index('--resume') + 1], sid)
        self.assertEqual(out['text'], 'second')

    def test_stale_session_falls_back_to_a_fresh_one(self):
        self._turn(_FakeProc(stdout='first', stderr='session_id: 20260913_010203_abc123'))
        out, calls = self._turn(
            _FakeProc(stderr='Session not found: 20260913_010203_abc123', returncode=1),
            _FakeProc(stdout='fresh', stderr='session_id: 20260913_020304_def456'),
        )
        self.assertEqual(len(calls), 2)
        self.assertIn('--resume', calls[0])
        self.assertNotIn('--resume', calls[1])
        self.assertEqual(out['text'], 'fresh')
        self.assertEqual(out['error'], '')

    def test_malformed_session_id_never_reaches_argv(self):
        self._turn(_FakeProc(stdout='first', stderr='session_id: ;touch${IFS}/tmp/x'))
        _, calls = self._turn(_FakeProc(stdout='second'))
        self.assertNotIn('--resume', calls[0])

    def test_session_line_is_not_reported_as_the_error(self):
        out, _ = self._turn(
            _FakeProc(stderr='provider exploded\nsession_id: 20260913_010203_abc123', returncode=1)
        )
        self.assertIn('provider exploded', out['error'])
        self.assertNotIn('session_id', out['error'])


class EngineHygieneTests(SimpleTestCase):
    """What the merchant sees must be Linda's answer, from Linda's prompt."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)

    def _turn(self, proc):
        with (
            mock.patch.object(eng, 'janus_cmd', return_value=['/opt/janus/bin/janus']),
            mock.patch.object(eng, 'linda_janus_home', return_value=self.home),
            mock.patch.object(eng.subprocess, 'run', return_value=proc),
        ):
            return run_janus_turn(message='hi', conversation_key='conv-1', system_prompt='p')

    def test_step_limit_notice_is_not_part_of_the_answer(self):
        out = self._turn(
            _FakeProc(
                stdout='⚠️  Reached maximum iterations (8). Requesting summary...\nStock is fine.'
            )
        )
        self.assertEqual(out['text'], 'Stock is fine.')

    def test_an_empty_reply_is_a_failure_not_a_blank_answer(self):
        for stdout in ('', '(empty)', '❌ All API retries exhausted with no successful response.'):
            out = self._turn(_FakeProc(stdout=stdout))
            self.assertEqual(out['error'], 'janus returned no reply', stdout)

    def test_home_carries_lindas_identity_and_no_general_janus_skills(self):
        home = self.home / 'conv' / eng._session_id('conv-1')
        bundled = home / 'skills' / 'github' / 'github-pr'
        learned = home / 'skills' / 'ops' / 'restock'
        for skill_dir, name in ((bundled, 'github-pr'), (learned, 'restock')):
            skill_dir.mkdir(parents=True)
            (skill_dir / 'SKILL.md').write_text(f'---\nname: {name}\n---\nx\n', encoding='utf-8')
        (home / 'skills' / '.bundled_manifest').write_text('github-pr:abc\n', encoding='utf-8')
        self._turn(_FakeProc(stdout='ok'))
        self.assertIn('You are Linda', (home / 'SOUL.md').read_text(encoding='utf-8'))
        self.assertTrue((home / '.no-bundled-skills').exists())
        self.assertFalse(bundled.exists())
        self.assertTrue(learned.exists())

    def test_config_keeps_turns_fast(self):
        body = eng._config_text('https://s/mcp/')
        self.assertIn('api_max_retries: 1', body)
        self.assertIn('supports_parallel_tool_calls: true', body)
        self.assertIn('resources: false', body)

    def test_engine_failures_read_as_what_happened(self):
        from core.assistant.runtime import _friendly_provider_error

        self.assertIn('took longer', _friendly_provider_error('janus timed out after 55s'))
        # 'generate' contains 'rate'; this once read as a provider rate limit.
        self.assertNotIn('rate limit', _friendly_provider_error('janus returned no reply'))


class SessionAndProgressTests(SimpleTestCase):
    """A turn resends only what it must, reports what it cost, and shows it is alive."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)
        self.conv = self.home / 'conv' / eng._session_id('conv-1')

    def _run(self, *procs, **kwargs):
        with (
            mock.patch.object(eng, 'janus_cmd', return_value=['/opt/janus/bin/janus']),
            mock.patch.object(eng, 'linda_janus_home', return_value=self.home),
            mock.patch.object(
                eng.subprocess,
                'run',
                side_effect=procs[0] if callable(procs[0]) else list(procs),
            ) as spawn,
        ):
            out = run_janus_turn(
                message='hi', conversation_key='conv-1', system_prompt='p', **kwargs
            )
        return out, [c.args[0] for c in spawn.call_args_list], spawn

    @staticmethod
    def _message(argv):
        return argv[argv.index('-q') + 1]

    def test_recap_goes_only_to_a_fresh_session(self):
        kw = {'history': 'Merchant: what sold yesterday?', 'turn_context': 'Page: Orders'}
        _, calls, _ = self._run(_FakeProc(stdout='a', stderr='session_id: s1'), **kw)
        first = self._message(calls[0])
        self.assertIn('what sold yesterday?', first)
        self.assertIn('Page: Orders', first)
        self.assertTrue(first.endswith("[The merchant's message]\nhi"))
        _, calls, _ = self._run(_FakeProc(stdout='b', stderr='session_id: s1'), **kw)
        self.assertIn('--resume', calls[0])
        self.assertNotIn('what sold yesterday?', self._message(calls[0]))
        self.assertIn('Page: Orders', self._message(calls[0]))

    def test_a_bare_message_is_sent_as_is(self):
        _, calls, spawn = self._run(_FakeProc(stdout='a'))
        self.assertEqual(self._message(calls[0]), 'hi')
        self.assertEqual(spawn.call_args.kwargs['env']['JANUS_EPHEMERAL_SYSTEM_PROMPT'], 'p')

    def test_a_long_or_idle_conversation_starts_a_fresh_session(self):
        import json as _json
        import time as _time

        for meta in (
            {'id': 's1', 'turns': eng.SESSION_MAX_TURNS, 'last_at': _time.time()},
            {'id': 's1', 'turns': 1, 'last_at': _time.time() - eng.SESSION_IDLE_S - 1},
        ):
            self.conv.mkdir(parents=True, exist_ok=True)
            (self.conv / 'janus_session.json').write_text(_json.dumps(meta), encoding='utf-8')
            _, calls, _ = self._run(_FakeProc(stdout='a'), history='Merchant: earlier')
            self.assertNotIn('--resume', calls[0])
            self.assertIn('earlier', self._message(calls[0]))

    def test_a_lost_session_retries_with_the_recap(self):
        self._run(_FakeProc(stdout='a', stderr='session_id: s1'))
        _, calls, _ = self._run(
            _FakeProc(stderr='Session not found: s1', returncode=1),
            _FakeProc(stdout='fresh', stderr='session_id: s2'),
            history='Merchant: earlier',
        )
        self.assertNotIn('earlier', self._message(calls[0]))
        self.assertIn('earlier', self._message(calls[1]))

    def _janus_writes_usage(self, sid, input_tokens, output_tokens):
        import sqlite3

        def fake(argv, **kwargs):
            home = Path(kwargs['env']['JANUS_HOME'])
            with sqlite3.connect(home / 'state.db') as db:
                db.execute(
                    'CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, model TEXT, '
                    'input_tokens INT, output_tokens INT, cache_read_tokens INT, '
                    'cache_write_tokens INT, reasoning_tokens INT, api_call_count INT, '
                    'estimated_cost_usd REAL)'
                )
                db.execute(
                    'INSERT OR REPLACE INTO sessions VALUES (?, ?, ?, ?, 0, 0, 0, 1, 0.01)',
                    (sid, 'deepseek-v4-pro', input_tokens, output_tokens),
                )
            return _FakeProc(stdout='ok', stderr=f'session_id: {sid}')

        return fake

    def test_turn_usage_is_what_this_turn_added(self):
        out, _, _ = self._run(self._janus_writes_usage('s1', 1000, 50))
        self.assertEqual((out['usage']['input_tokens'], out['usage']['output_tokens']), (1000, 50))
        self.assertEqual(out['usage']['model'], 'deepseek-v4-pro')
        out, _, _ = self._run(self._janus_writes_usage('s1', 2600, 90))
        self.assertEqual((out['usage']['input_tokens'], out['usage']['output_tokens']), (1600, 40))

    def test_janus_background_review_is_off(self):
        # Its thread swaps stdout/stderr process-wide; the reply printed meanwhile
        # was lost and the merchant got "no reply" (live, v0.68.0).
        body = eng._config_text('https://s/mcp/')
        self.assertIn('nudge_interval: 0', body)
        self.assertIn('creation_nudge_interval: 0', body)

    def test_a_reply_lost_from_stdout_is_recovered_from_state_db(self):
        import sqlite3
        import time as _time

        def silent(argv, **kwargs):
            home = Path(kwargs['env']['JANUS_HOME'])
            now = _time.time()
            with sqlite3.connect(home / 'state.db') as db:
                db.execute(
                    'CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, started_at REAL, model TEXT, '
                    'input_tokens INT, output_tokens INT, cache_read_tokens INT, cache_write_tokens INT, '
                    'reasoning_tokens INT, api_call_count INT, estimated_cost_usd REAL)'
                )
                db.execute(
                    'CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, '
                    'role TEXT, content TEXT, timestamp REAL)'
                )
                db.execute(
                    "INSERT INTO sessions VALUES ('s9', 'linda', ?, 'deepseek-v4-pro', 500, 20, 0, 0, 0, 3, 0)",
                    (now,),
                )
                db.execute(
                    "INSERT INTO messages (session_id, role, content, timestamp) VALUES ('s9', 'assistant', ?, ?)",
                    ('Three products need better titles.', now),
                )
            return _FakeProc(stdout='', stderr='')

        out, _, _ = self._run(silent)
        self.assertEqual(out['error'], '')
        self.assertEqual(out['text'], 'Three products need better titles.')
        self.assertEqual(out['usage']['output_tokens'], 20)
        self.assertEqual(eng._stored_session_id(self.conv), 's9')

    def test_the_turn_ticks_while_janus_works(self):
        import time as _time

        def slow(argv, **kwargs):
            _time.sleep(0.3)
            return _FakeProc(stdout='done')

        with (
            mock.patch.object(eng, 'janus_cmd', return_value=['/opt/janus/bin/janus']),
            mock.patch.object(eng, 'linda_janus_home', return_value=self.home),
            mock.patch.object(eng.subprocess, 'run', side_effect=slow),
        ):
            items = list(
                eng.iter_janus_turn(
                    message='hi', conversation_key='conv-1', system_prompt='p', tick_s=0.05
                )
            )
        self.assertGreaterEqual(items.count(None), 2)
        self.assertEqual(items[-1]['text'], 'done')

    @staticmethod
    def _works_with_steps(argv, **kwargs):
        import json as _json
        import time as _time

        progress = Path(kwargs['env']['JANUS_HOME']) / 'progress.jsonl'
        with progress.open('a', encoding='utf-8') as fh:
            fh.write(
                _json.dumps(
                    {'ev': 'start', 'tool': 'web_search', 'id': 'c1', 'args': {'query': 'tea'}}
                )
                + '\n'
            )
        _time.sleep(0.3)
        with progress.open('a', encoding='utf-8') as fh:
            fh.write(_json.dumps({'ev': 'end', 'tool': 'web_search', 'id': 'c1', 'status': 'ok'}))
            fh.write('\n')
        return _FakeProc(stdout='done')

    def _items(self, side_effect):
        with (
            mock.patch.object(eng, 'janus_cmd', return_value=['/opt/janus/bin/janus']),
            mock.patch.object(eng, 'linda_janus_home', return_value=self.home),
            mock.patch.object(eng.subprocess, 'run', side_effect=side_effect),
        ):
            return list(
                eng.iter_janus_turn(
                    message='hi', conversation_key='conv-1', system_prompt='p', tick_s=0.05
                )
            )

    def test_steps_stream_while_janus_works(self):
        items = self._items(self._works_with_steps)
        steps = [i for i in items if isinstance(i, dict) and i.get('type') == 'step']
        self.assertEqual([s['state'] for s in steps], ['running', 'done'])
        self.assertEqual(steps[0]['label'], 'Searching the web')
        # The last line, written just before Janus exited, still arrives.
        self.assertEqual(items[-1]['text'], 'done')
        self.assertLess(items.index(steps[-1]), len(items) - 1)

    def test_a_turn_never_replays_the_last_turns_steps(self):
        self.conv.mkdir(parents=True, exist_ok=True)
        (self.conv / 'progress.jsonl').write_text(
            '{"ev": "start", "tool": "web_search", "id": "old"}\n', encoding='utf-8'
        )
        items = self._items(lambda argv, **kw: _FakeProc(stdout='done'))
        self.assertFalse([i for i in items if isinstance(i, dict) and i.get('type')])

    def test_the_blocking_call_returns_the_reply_not_a_step(self):
        with (
            mock.patch.object(eng, 'janus_cmd', return_value=['/opt/janus/bin/janus']),
            mock.patch.object(eng, 'linda_janus_home', return_value=self.home),
            mock.patch.object(eng.subprocess, 'run', side_effect=self._works_with_steps),
        ):
            out = run_janus_turn(message='hi', conversation_key='conv-1', system_prompt='p')
        self.assertEqual(out['text'], 'done')


class AgentToolsetTests(SimpleTestCase):
    """What Linda can do beyond the store's tools, and what stays out on purpose."""

    def test_she_can_plan_recall_and_search_the_web(self):
        self.assertLessEqual({'todo', 'session_search', 'search'}, set(eng.turn_toolsets()))

    def test_web_search_comes_without_page_fetching(self):
        # 'web' would add web_extract: a fetch of a URL the model picks is an
        # outbound channel for whatever she has read (customers, orders).
        self.assertIn('search', eng.turn_toolsets())
        self.assertNotIn('web', eng.turn_toolsets())

    def test_subagents_stay_off_while_delegate_task_can_launch_a_program(self):
        # Janus 0.18.0: delegate_task hands model-supplied acp_command/acp_args
        # to subprocess.Popen (agent/copilot_acp_client.py). A prompt injection
        # in anything she reads could start any program as the app user. Hooks
        # can't guard it: Janus lets a call through when a hook fails.
        self.assertNotIn('delegation', eng.turn_toolsets())

    def test_the_merchant_can_switch_web_search_off(self):
        from core.assistant import janus_settings

        with mock.patch.object(janus_settings, 'web_search_enabled', return_value=False):
            toolsets = eng.turn_toolsets()
        self.assertNotIn('search', toolsets)
        self.assertIn('todo', toolsets)


class ProviderWiringTests(SimpleTestCase):
    """Janus's `auto` picks OpenRouter whenever OPENAI_API_KEY is set and never
    sees a dashboard-stored key, so the turn must pin Morpheus's provider."""

    def _wire(self, name, **cfg):
        from core.agents.provider_registry import ProviderConfig

        conf = ProviderConfig(
            provider=name,
            api_key=cfg.get('api_key', 'sk-test'),
            base_url=cfg.get('base_url', ''),
            model=cfg.get('model', ''),
            embedding_model='',
        )
        with (
            mock.patch('core.agents.provider_registry.get_active_provider_name', return_value=name),
            mock.patch('core.agents.provider_registry.get_provider_config', return_value=conf),
        ):
            return eng._provider_wiring()

    def test_dashboard_deepseek_key_reaches_janus(self):
        args, env = self._wire(
            'deepseek', model='deepseek-v4-pro', base_url='https://api.deepseek.com/v1'
        )
        self.assertEqual(args, ['--provider', 'deepseek', '-m', 'deepseek-v4-pro'])
        self.assertEqual(env['DEEPSEEK_API_KEY'], 'sk-test')
        self.assertEqual(env['DEEPSEEK_BASE_URL'], 'https://api.deepseek.com/v1')

    def test_openai_maps_to_the_direct_api_not_openrouter(self):
        args, _ = self._wire('openai', model='gpt-4o-mini')
        self.assertEqual(args[:2], ['--provider', 'openai-api'])

    def test_unmapped_provider_leaves_janus_to_resolve(self):
        self.assertEqual(self._wire('hermes'), ([], {}))

    def test_missing_key_leaves_janus_to_resolve(self):
        self.assertEqual(self._wire('deepseek', api_key=''), ([], {}))

    def test_provider_key_overrides_an_inherited_one(self):
        with mock.patch.dict(
            eng.os.environ, {'PATH': '/usr/bin', 'DEEPSEEK_API_KEY': 'stale'}, clear=True
        ):
            env = _child_env({'DEEPSEEK_API_KEY': 'from-dashboard'})
        self.assertEqual(env['DEEPSEEK_API_KEY'], 'from-dashboard')


class AssistantEngineTests(SimpleTestCase):
    """Janus is the only engine."""

    def test_tests_can_never_spawn_a_real_engine(self):
        from django.conf import settings

        self.assertFalse(Path(settings.JANUS_BIN).exists())

    def test_tests_can_never_install_a_janus(self):
        # With `janus` on a developer's PATH, a turn would start the updater.
        from django.conf import settings

        self.assertFalse(settings.LINDA_JANUS_AUTO_UPDATE)

    def test_no_engine_switch_remains(self):
        from django.conf import settings

        self.assertFalse(hasattr(settings, 'LINDA_ENGINE'))

    def test_identity_stays_linda(self):
        from core.assistant.prompts import LINDA_BASE_PROMPT

        self.assertIn('You are Linda', LINDA_BASE_PROMPT)
        self.assertIn('never needs the name of your engine', LINDA_BASE_PROMPT)

    def test_the_prompt_no_longer_rations_her_work(self):
        # The owner found Linda constrained (2026-10-09): she was told she had
        # "a few tool steps and well under a minute", and to stop at a sample.
        from core.assistant.prompts import LINDA_BASE_PROMPT

        for rationing in ('a few tool steps', 'well under a minute', 'do a sample'):
            self.assertNotIn(rationing, LINDA_BASE_PROMPT)
        self.assertIn("Every change needs the merchant's yes", LINDA_BASE_PROMPT)


class BundledEcommerceSkillsTests(SimpleTestCase):
    """Janus store homes must ship Morpheus daily-ops skills out of the box."""

    _REQUIRED = (
        'morpheus-store-operator',
        'morpheus-orders',
        'morpheus-catalog',
        'morpheus-content-seo',
    )

    def test_required_skills_are_present(self):
        names = bundled_skill_names()
        for name in self._REQUIRED:
            self.assertIn(name, names)

    def test_each_skill_has_valid_frontmatter(self):
        root = bundled_skills_dir()
        for skill_md in sorted(root.rglob('SKILL.md')):
            text = skill_md.read_text(encoding='utf-8')
            self.assertTrue(text.startswith('---'), skill_md)
            rest = text[3:]
            close = rest.find('\n---')
            self.assertGreater(close, 0, skill_md)
            fm = rest[:close]
            self.assertIn('name:', fm)
            self.assertIn('description:', fm)
            self.assertLessEqual(len(text), 100_000, skill_md)


class JanusHistoryTests(SimpleTestCase):
    def test_history_recap_keeps_the_conversation_not_tool_output(self):
        # A fresh Janus session (after a deploy wipes its state) needs a recap.
        # Tool rows once crowded the merchant's own questions out of it.
        from core.assistant.persistence import StoredMessage
        from core.assistant.runtime import _format_janus_history

        out = _format_janus_history(
            [
                StoredMessage(role='user', content='how many copies of Dune?'),
                StoredMessage(role='tool', tool_name='products.get', tool_output={'x': 'y' * 500}),
                StoredMessage(role='assistant', content='Four in stock.'),
            ]
        )
        self.assertIn('how many copies of Dune?', out)
        self.assertIn('Four in stock.', out)
        self.assertNotIn('products.get', out)

    def test_empty_history_adds_nothing(self):
        from core.assistant.runtime import _format_janus_history

        self.assertEqual(_format_janus_history([]), '')

"""scripts/deploy_guard.py: put back a store that did not come up (safe deploys, part 3)."""

from __future__ import annotations

import hashlib
import hmac
import http.server
import importlib.util
import json
import os
import socket
import subprocess
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    'deploy_guard', _ROOT / 'scripts' / 'deploy_guard.py'
)
guard = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(guard)

NEW, OLD = 'v0.121.0', 'v0.120.1'
TAGS = ['v0.119.0', 'v0.120.0', OLD, NEW]
UP_NEW = (200, json.dumps({'status': 'ok', 'version': NEW}))
UP_OLD = (200, json.dumps({'status': 'ok', 'version': OLD}))
DOWN = (503, '')
REFUSED = (403, '')


class _Clock:
    """A fake clock that only sleeping moves."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def _get(responses):
    """A fake GET: each URL answers from its list, one entry per call, the last repeating."""
    calls = {}

    def get(url, timeout=15):
        answers = responses[url]
        index = calls.get(url, 0)
        calls[url] = index + 1
        return answers[min(index, len(answers) - 1)]

    return get


class VersionTests(SimpleTestCase):
    def test_the_previous_release_ignores_other_tags_and_order(self):
        tags = ['v0.119.0', 'morpheus-known-good', NEW, 'v1.0.0-rc1', OLD, 'v0.9.9', 'v0.120.0']
        self.assertEqual(guard.previous_release(NEW, tags), OLD)
        self.assertEqual(guard.previous_release('v0.9.9', tags), None)

    def test_the_version_being_deployed_is_read_from_settings(self):
        text = "MORPHEUS_VERSION = config('MORPHEUS_VERSION', default='v0.121.0')\n"
        self.assertEqual(guard.expected_version(text), NEW)


class StateTests(SimpleTestCase):
    def test_a_refusal_is_not_an_unhealthy_answer(self):
        # A rule in front of the store refusing the guard says nothing about the store.
        self.assertEqual(
            guard.store_state('https://s', _get({'https://s/readyz': [REFUSED]}))[1], 'refused'
        )
        get = _get({'https://s/readyz': [UP_NEW], 'https://s/': [(429, '')]})
        self.assertEqual(guard.store_state('https://s', get)[1], 'refused')

    def test_ok_needs_readyz_and_the_home_page(self):
        get = _get({'https://s/readyz': [UP_NEW], 'https://s/': [(200, '')]})
        self.assertEqual(guard.store_state('https://s', get), (NEW, 'ok'))
        get = _get({'https://s/readyz': [UP_NEW], 'https://s/': [(500, '')]})
        self.assertEqual(guard.store_state('https://s', get), (NEW, 'bad'))


class ClassifyTests(SimpleTestCase):
    def _classify(self, responses, stores=('https://s',)):
        clock = _Clock()
        states = guard.classify_all(
            list(stores), NEW, get=_get(responses), sleep=clock.sleep, clock=clock
        )
        return states, clock.now

    def test_a_swap_of_two_minutes_is_not_down(self):
        # A container swap answers 503 for a minute or more (80 s on dotbooks).
        responses = {'https://s/readyz': [DOWN] * 6 + [UP_NEW], 'https://s/': [(200, '')]}
        states, waited = self._classify(responses)
        self.assertEqual(states, {'https://s': 'up'})
        self.assertGreaterEqual(waited, 120)

    def test_a_store_still_on_the_old_version_is_left_alone(self):
        states, _ = self._classify({'https://s/readyz': [UP_OLD], 'https://s/': [(200, '')]})
        self.assertEqual(states, {'https://s': 'late'})

    def test_down_means_no_healthy_answer_for_the_whole_window(self):
        states, waited = self._classify({'https://s/readyz': [DOWN]})
        self.assertEqual(states, {'https://s': 'down'})
        self.assertGreaterEqual(waited, guard.DOWN_AFTER)

    def test_the_stores_share_one_window(self):
        responses = {'https://a/readyz': [DOWN], 'https://b/readyz': [DOWN]}
        states, waited = self._classify(responses, stores=('https://a', 'https://b'))
        self.assertEqual(set(states.values()), {'down'})
        self.assertLess(waited, guard.DOWN_AFTER + 2 * guard.CHECK_GAP)

    def test_a_store_that_refuses_the_guard_is_unknown_not_down(self):
        states, _ = self._classify({'https://s/readyz': [REFUSED]})
        self.assertEqual(states, {'https://s': 'unknown'})

    def test_a_home_page_that_fails_is_not_up(self):
        states, _ = self._classify({'https://s/readyz': [UP_NEW], 'https://s/': [(500, '')]})
        self.assertEqual(states, {'https://s': 'down'})


class MalformedAnswerTests(SimpleTestCase):
    def test_a_malformed_answer_is_unhealthy_not_a_crash(self):
        # BadStatusLine is an http.client.HTTPException, which URLError does not cover.
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        self.addCleanup(listener.close)

        def serve():
            conn, _ = listener.accept()
            conn.recv(1024)
            conn.sendall(b'NOT HTTP AT ALL\r\n\r\n')
            conn.close()

        threading.Thread(target=serve, daemon=True).start()
        port = listener.getsockname()[1]
        self.assertEqual(guard.http_get(f'http://127.0.0.1:{port}/readyz', timeout=5), (0, ''))


class _FakeCoolify(http.server.BaseHTTPRequestHandler):
    seen: list = []

    def do_POST(self):  # noqa: N802 — the stdlib's name
        body = self.rfile.read(int(self.headers['Content-Length']))
        # The message object, not a dict: urllib sends 'X-github-event', and HTTP
        # header names are case-insensitive, as the object's lookups are.
        type(self).seen.append((self.path, self.headers, body))
        reply = json.dumps([{'status': 'success', 'message': 'Deployment queued.'}]).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(reply)

    def log_message(self, *args):
        pass


class WebhookTests(SimpleTestCase):
    def test_the_push_is_signed_with_the_store_s_own_secret(self):
        _FakeCoolify.seen = []
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), _FakeCoolify)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        hook = f'http://127.0.0.1:{server.server_port}/webhooks/source/github/events/manual'
        status, text = guard.deploy_commit(hook, 'magnetoid/morpheus', 'main', 's3cret', 'c' * 40)
        self.assertEqual(status, 200)
        self.assertTrue(guard.queued(text))
        path, headers, body = _FakeCoolify.seen[0]
        self.assertEqual(path, '/webhooks/source/github/events/manual')
        self.assertEqual(headers['X-GitHub-Event'], 'push')
        expected = 'sha256=' + hmac.new(b's3cret', body, hashlib.sha256).hexdigest()
        self.assertEqual(headers['X-Hub-Signature-256'], expected)
        payload = json.loads(body)
        self.assertEqual(
            (payload['ref'], payload['after'], payload['repository']['full_name']),
            ('refs/heads/main', 'c' * 40, 'magnetoid/morpheus'),
        )

    def test_an_answer_without_a_queued_deployment_is_not_success(self):
        self.assertFalse(
            guard.queued(json.dumps([{'status': 'failed', 'message': 'Invalid signature.'}]))
        )
        self.assertFalse(guard.queued('not json'))


class TargetTests(SimpleTestCase):
    def test_a_store_goes_back_to_the_release_it_served_before(self):
        # v0.120.1 already failed on this store and it was put back on v0.120.0.
        self.assertEqual(
            guard.target_release('https://x', NEW, TAGS, {'https://x': 'v0.120.0'}), 'v0.120.0'
        )

    def test_without_a_before_version_the_previous_release_is_used(self):
        self.assertEqual(guard.target_release('https://x', NEW, TAGS, {}), OLD)

    def test_a_before_version_that_is_not_an_older_release_is_ignored(self):
        self.assertEqual(guard.target_release('https://x', NEW, TAGS, {'https://x': NEW}), OLD)
        self.assertEqual(guard.target_release('https://x', NEW, TAGS, {'https://x': 'dev'}), OLD)

    def test_the_before_file_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'before.txt'
            path.write_text('https://a v0.120.1\nhttps://b/ v0.119.0\njunk\n')
            self.assertEqual(
                guard.read_before(str(path)), {'https://a': OLD, 'https://b': 'v0.119.0'}
            )
        self.assertEqual(guard.read_before(''), {})
        self.assertEqual(guard.read_before('/no/such/file'), {})


class RollbackTests(SimpleTestCase):
    CONFIG = {
        'webhook': 'https://coolify/webhooks/source/github/events/manual',
        'repository': 'magnetoid/morpheus',
        'branch': 'main',
        'stores': {'https://up': 'a', 'https://late': 'b', 'https://down': 'c'},
    }
    COMMITS = {OLD: 'd' * 40, 'v0.120.0': 'e' * 40}

    def _run(
        self,
        after=(UP_OLD,),
        *,
        before=None,
        dry_run=False,
        contract='',
        post_answer=None,
        readyz_down=DOWN,
    ):
        posts, lines, clock = [], [], _Clock()
        after = list(after)

        def get(url, timeout=15):
            if url == 'https://down/readyz':
                # Down until its webhook is sent, then whatever the rollback brings.
                return (
                    after.pop(0)
                    if posts and len(after) > 1
                    else (after[0] if posts else readyz_down)
                )
            return {
                'https://up/readyz': UP_NEW,
                'https://late/readyz': UP_OLD,
            }.get(url, (200, ''))

        def post(url, body, headers, timeout=30):
            posts.append((url, json.loads(body), headers))
            return post_answer or (200, '[{"status": "success"}]')

        code = guard.rollback(
            self.CONFIG,
            NEW,
            TAGS,
            dry_run=dry_run,
            before=before or {},
            get=get,
            post=post,
            sleep=clock.sleep,
            clock=clock,
            commit_of=self.COMMITS.__getitem__,
            contract_of=lambda release: contract,
            log=lines.append,
        )
        return code, posts, '\n'.join(lines)

    def test_only_the_store_that_is_down_is_put_back(self):
        code, posts, log = self._run()
        self.assertEqual(code, 1)  # a rollback is still a failed release
        self.assertEqual(len(posts), 1)
        url, payload, headers = posts[0]
        self.assertEqual(payload['after'], 'd' * 40)
        expected = (
            'sha256=' + hmac.new(b'c', json.dumps(payload).encode(), hashlib.sha256).hexdigest()
        )
        self.assertEqual(headers['X-Hub-Signature-256'], expected)
        self.assertIn('OK    https://down serves v0.120.1 again', log)
        self.assertIn('LATE  https://late', log)
        self.assertIn('UP    https://up', log)

    def test_a_store_goes_back_to_the_release_it_ran_before_this_deploy(self):
        code, posts, log = self._run(
            after=((200, json.dumps({'status': 'ok', 'version': 'v0.120.0'})),),
            before={'https://down': 'v0.120.0'},
        )
        self.assertEqual(posts[0][1]['after'], 'e' * 40)
        self.assertIn('OK    https://down serves v0.120.0 again', log)

    def test_going_back_past_a_contract_is_refused(self):
        code, posts, log = self._run(
            before={'https://down': 'v0.120.0'}, contract='core/migrations/0030_x.py'
        )
        self.assertEqual(code, 1)
        self.assertEqual(posts, [])
        self.assertIn('core/migrations/0030_x.py', log)
        self.assertIn('by hand', log)

    def test_a_dry_run_sends_nothing(self):
        code, posts, log = self._run(dry_run=True)
        self.assertEqual(posts, [])
        self.assertIn('would put back v0.120.1', log)
        self.assertEqual(code, 1)

    def test_a_webhook_that_queues_nothing_is_a_failure(self):
        code, posts, log = self._run(post_answer=(200, '[{"status": "failed"}]'))
        self.assertEqual(code, 1)
        self.assertIn('FAIL  https://down', log)

    def test_a_store_that_stays_down_after_the_rollback_is_reported(self):
        code, _, log = self._run(after=(DOWN,))
        self.assertEqual(code, 1)
        self.assertIn('did not come up on v0.120.1 either', log)

    def test_a_store_that_comes_up_on_the_new_version_after_all_is_reported(self):
        code, _, log = self._run(after=(UP_NEW, UP_OLD))
        self.assertIn('came up on v0.121.0 after all', log)
        self.assertIn('OK    https://down serves v0.120.1 again', log)

    def test_a_store_that_refuses_the_guard_is_left_alone_and_reported(self):
        code, posts, log = self._run(readyz_down=REFUSED)
        self.assertEqual(code, 1)
        self.assertEqual(posts, [])
        self.assertIn('cannot tell', log)

    def test_every_store_up_or_late_is_success(self):
        config = dict(self.CONFIG, stores={'https://up': 'a', 'https://late': 'b'})
        clock = _Clock()
        code = guard.rollback(
            config,
            NEW,
            TAGS,
            get=lambda url, timeout=15: {
                'https://up/readyz': UP_NEW,
                'https://late/readyz': UP_OLD,
            }.get(url, (200, '')),
            post=None,
            sleep=clock.sleep,
            clock=clock,
            log=lambda line: None,
        )
        self.assertEqual(code, 0)


class ConfigTests(SimpleTestCase):
    def test_without_its_secret_the_guard_says_rollback_is_off(self):
        with patch.dict('os.environ', {}, clear=True), self.assertRaises(SystemExit) as stop:
            guard.load_config()
        self.assertIn('Automatic rollback is off', str(stop.exception))

    def test_a_config_without_stores_is_refused(self):
        env = {'MORPHEUS_DEPLOY_HOOKS': json.dumps({'webhook': 'https://x', 'repository': 'a/b'})}
        with patch.dict('os.environ', env, clear=True), self.assertRaises(SystemExit):
            guard.load_config()


class _FakeStore(http.server.BaseHTTPRequestHandler):
    commit = ''  # what the store's /readyz reports; '' = a host that does not say

    def do_GET(self):  # noqa: N802 — the stdlib's name
        payload = {'status': 'ok', 'version': settings.MORPHEUS_VERSION, 'commit': self.commit}
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class SmokeRecordsTests(SimpleTestCase):
    def test_the_smoke_records_what_each_store_served_before(self):
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), _FakeStore)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        base = f'http://127.0.0.1:{server.server_port}'
        with tempfile.TemporaryDirectory() as tmp:
            before = Path(tmp) / 'before.txt'
            env = dict(
                os.environ,
                SMOKE_BASE_URLS=base,
                SMOKE_DEADLINE_SECS='30',
                SMOKE_BEFORE_FILE=str(before),
            )
            done = subprocess.run(
                ['bash', 'scripts/deploy_smoke.sh'],
                cwd=_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertEqual(before.read_text().split(), [base, settings.MORPHEUS_VERSION])


class WorkflowTests(SimpleTestCase):
    def test_deploy_smoke_runs_the_guard_when_the_smoke_fails(self):
        text = (_ROOT / '.github' / 'workflows' / 'deploy-smoke.yml').read_text()
        self.assertIn('fetch-depth: 0', text)
        self.assertIn("if: failure() && steps.smoke.outcome == 'failure'", text)
        self.assertIn('python3 scripts/deploy_guard.py rollback', text)
        self.assertIn('secrets.MORPHEUS_DEPLOY_HOOKS', text)
        self.assertIn('SMOKE_BEFORE_FILE', text)

    def test_after_a_green_smoke_the_guard_checks_it_can_see_the_stores(self):
        text = (_ROOT / '.github' / 'workflows' / 'deploy-smoke.yml').read_text()
        self.assertIn('python3 scripts/deploy_guard.py rollback --dry-run', text)


class SmokeWaitsForTheCommitTests(SimpleTestCase):
    """A push that keeps the version (docs only) used to pass the smoke at once,
    and the live-store audits then ran into the store's container swap (503)."""

    def _smoke(self, live_commit, expected_commit):
        handler = type('Store', (_FakeStore,), {'commit': live_commit})
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        env = dict(
            os.environ,
            SMOKE_BASE_URLS=f'http://127.0.0.1:{server.server_port}',
            SMOKE_DEADLINE_SECS='1',
            SMOKE_POLL_SECS='1',
            SMOKE_EXPECT_COMMIT=expected_commit,
        )
        return subprocess.run(
            ['bash', 'scripts/deploy_smoke.sh'],
            cwd=_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    def test_a_store_still_on_another_commit_is_waited_for(self):
        done = self._smoke('b' * 40, 'a' * 40)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn('commit=bbbbbbb', done.stdout + done.stderr)

    def test_a_store_on_the_pushed_commit_passes(self):
        done = self._smoke('a' * 40, 'A' * 40)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_a_store_that_reports_no_commit_passes_on_its_version(self):
        done = self._smoke('', 'a' * 40)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

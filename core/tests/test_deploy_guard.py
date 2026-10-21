"""scripts/deploy_guard.py: put back a store that did not come up (safe deploys, part 3)."""

from __future__ import annotations

import hashlib
import hmac
import http.server
import importlib.util
import json
import threading
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

_SPEC = importlib.util.spec_from_file_location(
    'deploy_guard', Path(__file__).resolve().parents[2] / 'scripts' / 'deploy_guard.py'
)
guard = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(guard)

NEW, OLD = 'v0.121.0', 'v0.120.1'
UP_NEW = (200, json.dumps({'status': 'ok', 'version': NEW}))
UP_OLD = (200, json.dumps({'status': 'ok', 'version': OLD}))
DOWN = (503, '')


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
        tags = [
            'v0.119.0',
            'morpheus-known-good',
            'v0.121.0',
            'v1.0.0-rc1',
            'v0.120.1',
            'v0.9.9',
            'v0.120.0',
        ]
        self.assertEqual(guard.previous_release(NEW, tags), OLD)
        self.assertEqual(guard.previous_release('v0.9.9', tags), None)

    def test_the_version_being_deployed_is_read_from_settings(self):
        text = "MORPHEUS_VERSION = config('MORPHEUS_VERSION', default='v0.121.0')\n"
        self.assertEqual(guard.expected_version(text), NEW)


class ClassifyTests(SimpleTestCase):
    def _classify(self, readyz, home=(200, '')):
        get = _get({'https://s/readyz': readyz, 'https://s/': [home]})
        sleeps = []
        return guard.classify('https://s', NEW, get=get, sleep=sleeps.append), sleeps

    def test_a_store_on_the_new_version_is_up(self):
        self.assertEqual(self._classify([UP_NEW])[0], 'up')

    def test_a_store_still_on_the_old_version_is_left_alone(self):
        self.assertEqual(self._classify([UP_OLD])[0], 'late')

    def test_a_brief_503_is_not_down(self):
        state, sleeps = self._classify([DOWN, UP_NEW])
        self.assertEqual(state, 'up')
        self.assertEqual(sleeps, [guard.CHECK_GAP])

    def test_down_means_down_at_every_check(self):
        state, sleeps = self._classify([DOWN])
        self.assertEqual(state, 'down')
        self.assertEqual(len(sleeps), guard.CHECKS - 1)

    def test_a_home_page_that_fails_is_not_up(self):
        self.assertEqual(self._classify([UP_NEW], home=(500, ''))[0], 'down')


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


class RollbackTests(SimpleTestCase):
    CONFIG = {
        'webhook': 'https://coolify/webhooks/source/github/events/manual',
        'repository': 'magnetoid/morpheus',
        'branch': 'main',
        'stores': {'https://up': 'a', 'https://late': 'b', 'https://down': 'c'},
    }

    def _run(self, down_after=(DOWN,), dry_run=False, post_answer=(200, '[{"status": "success"}]')):
        get = _get(
            {
                'https://up/readyz': [UP_NEW],
                'https://up/': [(200, '')],
                'https://late/readyz': [UP_OLD],
                'https://late/': [(200, '')],
                'https://down/readyz': [DOWN] * guard.CHECKS + list(down_after),
                'https://down/': [(200, '')],
            }
        )
        posts, lines = [], []

        def post(url, body, headers, timeout=30):
            posts.append((url, json.loads(body), headers))
            return post_answer

        code = guard.rollback(
            self.CONFIG,
            NEW,
            ['v0.120.0', OLD, NEW],
            dry_run=dry_run,
            get=get,
            post=post,
            sleep=lambda s: None,
            commit_of=lambda tag: {OLD: 'd' * 40}[tag],
            log=lines.append,
            clock=iter(range(0, 10_000, 30)).__next__,
        )
        return code, posts, '\n'.join(lines)

    def test_only_the_store_that_is_down_is_put_back_on_the_previous_release(self):
        code, posts, log = self._run(down_after=(DOWN, UP_OLD))
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

    def test_a_dry_run_sends_nothing(self):
        code, posts, log = self._run(dry_run=True)
        self.assertEqual(posts, [])
        self.assertIn('would put back v0.120.1', log)

    def test_a_webhook_that_queues_nothing_is_a_failure(self):
        code, posts, log = self._run(post_answer=(200, '[{"status": "failed"}]'))
        self.assertEqual(code, 1)
        self.assertIn('FAIL  https://down', log)

    def test_a_store_that_stays_down_after_the_rollback_is_reported(self):
        code, _, log = self._run(down_after=(DOWN,))
        self.assertEqual(code, 1)
        self.assertIn('did not come up on v0.120.1 either', log)


class ConfigTests(SimpleTestCase):
    def test_without_its_secret_the_guard_says_rollback_is_off(self):
        with patch.dict('os.environ', {}, clear=True), self.assertRaises(SystemExit) as stop:
            guard.load_config()
        self.assertIn('Automatic rollback is off', str(stop.exception))

    def test_a_config_without_stores_is_refused(self):
        env = {'MORPHEUS_DEPLOY_HOOKS': json.dumps({'webhook': 'https://x', 'repository': 'a/b'})}
        with patch.dict('os.environ', env, clear=True), self.assertRaises(SystemExit):
            guard.load_config()

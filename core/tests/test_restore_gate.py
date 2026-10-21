"""While a restore runs, every page says so (safe deploys, part 4)."""

from __future__ import annotations

import json
import os
import tempfile
import time
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from core import restore


class _StateFolder:
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = patch.dict(os.environ, {'MORPHEUS_BACKUP_DIR': tmp.name})
        env.start()
        self.addCleanup(env.stop)

    def _running(self, age=0.0, info=None):
        path = restore.running_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(info or {'file': 'b.tar.gz', 'state': 'running'}))
        stamp = time.time() - age
        os.utime(path, (stamp, stamp))
        return path


class GateTests(_StateFolder, TestCase):
    def test_every_page_says_restoring_while_a_restore_runs(self):
        self._running()
        for path in ('/', '/dashboard/', '/graphql/', '/readyz'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 503, path)
            self.assertContains(response, 'Restoring the store', status_code=503)
            self.assertEqual(response['Retry-After'], '30')
            self.assertEqual(response['Cache-Control'], 'no-store')

    def test_the_liveness_probe_stays_open(self):
        # It reads nothing, and a failing one could get the container replaced mid-restore.
        self._running()
        self.assertEqual(self.client.get('/healthz').status_code, 200)

    def test_no_restore_no_gate(self):
        self.assertNotEqual(self.client.get('/dashboard/').status_code, 503)

    def test_a_restore_that_stopped_beating_no_longer_closes_the_store(self):
        self._running(age=restore.STALE_AFTER + 5)
        self.assertNotEqual(self.client.get('/dashboard/').status_code, 503)


class GatePlacementTests(SimpleTestCase):
    def test_the_gate_runs_before_anything_reads_the_database(self):
        stack = settings.MIDDLEWARE
        gate = stack.index('core.restore.RestoreGateMiddleware')
        self.assertLess(gate, stack.index('django.contrib.sessions.middleware.SessionMiddleware'))
        self.assertLess(gate, stack.index('core.storefront_cache.StorefrontCacheMiddleware'))

    def test_reused_connections_are_checked_first(self):
        # A restore ends every other database session; a dead connection must be
        # replaced, not fail the request that picks it up.
        self.assertTrue(settings.DATABASES['default'].get('CONN_HEALTH_CHECKS'))


class LockTests(_StateFolder, SimpleTestCase):
    def test_a_second_restore_is_refused_while_one_runs(self):
        restore.start({'file': 'a'})
        with self.assertRaises(restore.RestoreBusy):
            restore.start({'file': 'b'})
        self.assertEqual(json.loads(restore.running_path().read_text())['file'], 'a')

    def test_a_dead_restore_is_taken_over(self):
        self._running(age=restore.STALE_AFTER + 5, info={'file': 'old'})
        restore.start({'file': 'new'})
        self.assertEqual(json.loads(restore.running_path().read_text())['file'], 'new')
        self.assertTrue(restore.is_running())

    def test_finish_records_the_outcome_and_opens_the_store(self):
        restore.start({'file': 'a'})
        restore.finish({'state': 'done', 'file': 'a'})
        self.assertFalse(restore.is_running())
        self.assertEqual(restore.last(), {'state': 'done', 'file': 'a'})

    def test_stalled_names_the_restore_that_stopped(self):
        self._running(age=restore.STALE_AFTER + 5, info={'file': 'x', 'state': 'running'})
        self.assertEqual(restore.stalled()['file'], 'x')
        self.assertFalse(restore.is_running())

    def test_nothing_stalled_while_a_restore_beats(self):
        self._running()
        self.assertIsNone(restore.stalled())

    def test_nothing_before_the_first_restore(self):
        self.assertIsNone(restore.last())
        self.assertIsNone(restore.stalled())
        self.assertFalse(restore.is_running())

    def test_the_heartbeat_keeps_the_restore_alive(self):
        path = self._running(age=restore.STALE_AFTER - 1)
        with restore.heartbeat(path, every=0.05):
            time.sleep(0.3)
        self.assertLess(time.time() - path.stat().st_mtime, 5)

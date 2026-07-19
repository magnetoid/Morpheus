"""Regression — sweep_stuck_runs reaps AgentRuns wedged after a worker died.

Guards Fix 16: every transition off 'running'/'queued' happens in-process, so a
killed worker (Coolify --force-recreate, OOM, hard time-limit) leaves the row
non-terminal with ended_at=NULL forever. ``sweep_stuck_runs(older_than_minutes)``
fails rows whose started_at is older than the cutoff — but EXCLUDES
'awaiting_approval' (a legitimate human-wait) and never touches terminal rows.

``started_at`` is auto_now_add, so rows are aged via a follow-up
``.update(started_at=...)``. Under tests CELERY_TASK_ALWAYS_EAGER is on, so
``sweep_stuck_runs.delay(...).get()`` runs inline and returns the result dict.
"""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from plugins.installed.agent_core.models import AgentRun
from plugins.installed.agent_core.tasks import sweep_stuck_runs


def _run(state: str, minutes_ago: int) -> AgentRun:
    run = AgentRun.objects.create(agent_name='reaper_test', user_message='go', state=state)
    old = timezone.now() - timedelta(minutes=minutes_ago)
    AgentRun.objects.filter(pk=run.pk).update(started_at=old)
    return run


class StuckRunSweeperTests(TestCase):
    def test_old_running_run_is_failed(self):
        run = _run('running', minutes_ago=20)

        sweep_stuck_runs.delay().get()

        run.refresh_from_db()
        self.assertEqual(run.state, 'failed')
        self.assertIsNotNone(run.ended_at)
        self.assertIn('orphan', run.error.lower())
        self.assertIn('worker', run.error.lower())

    def test_old_queued_run_is_failed(self):
        run = _run('queued', minutes_ago=20)

        sweep_stuck_runs.delay().get()

        run.refresh_from_db()
        self.assertEqual(run.state, 'failed')
        self.assertIsNotNone(run.ended_at)

    def test_young_running_run_is_left_alone(self):
        run = _run('running', minutes_ago=2)  # inside the 15-min cutoff

        sweep_stuck_runs.delay().get()

        run.refresh_from_db()
        self.assertEqual(run.state, 'running')
        self.assertIsNone(run.ended_at)

    def test_awaiting_approval_is_excluded(self):
        run = _run('awaiting_approval', minutes_ago=20)  # legit human-wait

        sweep_stuck_runs.delay().get()

        run.refresh_from_db()
        self.assertEqual(run.state, 'awaiting_approval')
        self.assertIsNone(run.ended_at)

    def test_completed_run_is_untouched(self):
        run = _run('completed', minutes_ago=20)

        sweep_stuck_runs.delay().get()

        run.refresh_from_db()
        self.assertEqual(run.state, 'completed')

    def test_return_value_reports_swept_count(self):
        _run('running', minutes_ago=20)
        _run('queued', minutes_ago=20)
        _run('awaiting_approval', minutes_ago=20)  # excluded
        _run('running', minutes_ago=2)  # too young

        result = sweep_stuck_runs.delay().get()

        self.assertTrue(result['ok'])
        self.assertEqual(result['swept'], 2)

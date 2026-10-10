"""Core's scheduled jobs are in the schedule the scheduler actually reads.

``morph/celery.py`` assigned its jobs to ``app.conf.beat_schedule``, but Celery
takes its configuration from Django settings and the first read of
``app.conf`` loaded it from there — silently replacing the assignment. So the
error-log prune, the update check, the outbox drain, the daily briefing and the
health check had never run in production, while every app's own jobs (added to
``settings.CELERY_BEAT_SCHEDULE``) did.
"""

from __future__ import annotations

from django.test import SimpleTestCase

CORE_JOBS = (
    'core-health-nightly',
    'core-errors-digest',
    'core-errors-prune',
    'core-check-for-updates',
    'core-outbox-publish',
    'assistant-daily-briefing',
    'core-sign-ins-prune',
)


class CoreBeatScheduleTests(SimpleTestCase):
    def test_core_jobs_are_in_the_effective_schedule(self):
        from morph.celery import app

        schedule = app.conf.beat_schedule
        for job in CORE_JOBS:
            with self.subTest(job=job):
                self.assertIn(job, schedule)

    def test_app_jobs_are_still_there(self):
        from morph.celery import app

        self.assertIn('feature_adoption.flush', app.conf.beat_schedule)

    def test_self_improvement_jobs_are_in_the_effective_schedule(self):
        # Registered from morph/celery.py inside a ``try/except: pass`` — the
        # shape that once silently dropped core's own jobs. Nothing asserted
        # them until now.
        from core.self_improvement.tasks import register_beat_schedule
        from morph.celery import app

        expected: dict = {}
        register_beat_schedule(expected)
        self.assertTrue(expected)
        for job in expected:
            with self.subTest(job=job):
                self.assertIn(job, app.conf.beat_schedule)

    def test_every_scheduled_task_is_one_the_worker_registers(self):
        # Beat sends a task by NAME. A schedule entry naming a task under its
        # module path while the task registers under an explicit ``name=`` is
        # rejected by the worker as unregistered — silently, as far as the
        # schedule is concerned. feature_adoption's hourly flush shipped that
        # way, so no store ever got a FeatureUsageDay row.
        from morph.celery import app

        app.loader.import_default_modules()
        unknown = {
            entry: spec['task']
            for entry, spec in app.conf.beat_schedule.items()
            if spec.get('task') not in app.tasks
        }
        self.assertEqual(unknown, {})

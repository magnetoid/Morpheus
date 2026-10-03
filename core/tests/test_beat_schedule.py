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

        self.assertIn('observability.rollup_hourly', app.conf.beat_schedule)

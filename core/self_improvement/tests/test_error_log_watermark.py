"""Regression: the error_log collector watermark must not collapse to now−10min.

Bug (fixed): `_last_successful_run()` filtered
`SiIngestJob.objects.filter(collector=..., status='ok')` — but `Collector.execute()`
opens THIS run's job with status='ok' + finished_at=NULL *before* the generator
body runs, so the query returned the current run's own row → `since` collapsed to
now−10min on every run and the collector silently dropped every error older than
~10 minutes (~83% of them). The fix adds `finished_at__isnull=False` so only
COMPLETED jobs count toward the watermark.

These tests drive the fix END-TO-END through `.execute()` (the old collector
tests called `.run()` directly and so never opened the in-progress job that
triggered the bug).
"""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.errors.models import ErrorEvent
from core.self_improvement.collectors.error_log import ErrorLogCollector
from core.self_improvement.models import SiIngestJob, SiSignal


class ErrorLogWatermarkExecuteTests(TestCase):
    def test_execute_does_not_collapse_watermark_to_now(self) -> None:
        """An error 30 min old, with a prior COMPLETED run 1h ago, must still be
        collected by execute() — proving the in-progress job execute() opens for
        THIS run did not drag the watermark forward to now−10min."""
        now = timezone.now()

        # An error that landed ~30 minutes ago. created_at is auto_now_add, so
        # stamp it explicitly after creation.
        ev = ErrorEvent.objects.create(
            kind='server',
            level='error',
            fingerprint='wm-30min',
            exception_class='ValueError',
            message='boom',
            traceback='Traceback...\n  File "/app/plugins/x.py", line 9, in view\n    ...',
            path='/products/',
        )
        thirty_min_ago = now - timedelta(minutes=30)
        ErrorEvent.objects.filter(pk=ev.pk).update(created_at=thirty_min_ago)

        # A prior COMPLETED run ~1h ago → watermark looks back to ~1h10min ago,
        # which INCLUDES the 30-min-old event.
        one_hour_ago = now - timedelta(hours=1)
        SiIngestJob.objects.create(
            collector='error_log',
            started_at=one_hour_ago,
            finished_at=one_hour_ago,
            status='ok',
        )

        emitted = ErrorLogCollector().execute()

        self.assertEqual(emitted, 1)
        self.assertTrue(
            SiSignal.objects.filter(source='error_log').exists(),
            'execute() dropped the 30-min-old error — watermark collapsed to now−10min',
        )

    def test_execute_opens_its_own_job_but_ignores_it_for_watermark(self) -> None:
        """Sanity check on the mechanism: execute() writes an ingest job for this
        run, yet a COMPLETED prior job is the one that sets the watermark."""
        now = timezone.now()
        ev = ErrorEvent.objects.create(
            kind='server',
            level='error',
            fingerprint='wm-20min',
            exception_class='KeyError',
            message='missing',
            path='/products/',
        )
        ErrorEvent.objects.filter(pk=ev.pk).update(created_at=now - timedelta(minutes=20))
        SiIngestJob.objects.create(
            collector='error_log',
            started_at=now - timedelta(hours=1),
            finished_at=now - timedelta(hours=1),
            status='ok',
        )

        ErrorLogCollector().execute()

        # Two jobs now exist for error_log: the prior completed one + the one
        # execute() just finished. Both are 'ok' + finished.
        self.assertEqual(SiIngestJob.objects.filter(collector='error_log').count(), 2)
        self.assertTrue(SiSignal.objects.filter(source='error_log').exists())


class LastSuccessfulRunTests(TestCase):
    def test_ignores_unfinished_job_uses_finished_one(self) -> None:
        """`_last_successful_run()` must derive the watermark from the most recent
        FINISHED job, never from an in-progress (finished_at=NULL) one — even
        though the unfinished job has the newer started_at."""
        now = timezone.now()

        # In-progress job (what execute() opens for the current run): newest
        # started_at, but finished_at is NULL.
        SiIngestJob.objects.create(
            collector='error_log',
            started_at=now,
            finished_at=None,
            status='ok',
        )
        # Older, COMPLETED job — the one the watermark should be derived from.
        finished_started = now - timedelta(hours=2)
        SiIngestJob.objects.create(
            collector='error_log',
            started_at=finished_started,
            finished_at=now - timedelta(hours=2) + timedelta(seconds=5),
            status='ok',
        )

        watermark = ErrorLogCollector()._last_successful_run()

        # Method returns prev.started_at - 10min, where prev is the FINISHED job.
        self.assertEqual(watermark, finished_started - timedelta(minutes=10))
        # And crucially NOT derived from the unfinished job (started at `now`).
        self.assertLess(watermark, now - timedelta(hours=1))

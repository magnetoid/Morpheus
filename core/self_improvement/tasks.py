"""Celery tasks for the self-improvement engine.

Schedule (registered in morph/celery.py:beat_schedule via this module's
import — Celery auto-discovers shared_task definitions):

  - ingest_hourly        (cron minute=7)
  - scan_seo_daily       (cron 03:30)
  - scan_drift_daily     (cron 04:30)
  - scan_code_weekly     (cron Mon 05:00)
  - analyze_nightly      (cron 04:00)
  - digest_weekly        (cron Mon 09:00)

The actual beat_schedule registration is done in morph/celery.py once
this module is imported (Celery's @shared_task decorator handles
discovery).
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger('morpheus.self_improvement.tasks')


@shared_task(name='self_improvement.ingest_hourly')
def ingest_hourly() -> dict:
    """Run the hour-cadenced collectors (error_log; csp is hook-driven)."""
    from core.self_improvement.collectors.error_log import ErrorLogCollector  # noqa: PLC0415

    return {'error_log': ErrorLogCollector().execute()}


@shared_task(name='self_improvement.scan_seo_daily')
def scan_seo_daily() -> dict:
    from core.self_improvement.collectors.seo_gap import SeoGapCollector  # noqa: PLC0415

    return {'seo_gap': SeoGapCollector().execute()}


@shared_task(name='self_improvement.scan_drift_daily')
def scan_drift_daily() -> dict:
    from core.self_improvement.collectors.upstream_drift import (  # noqa: PLC0415
        UpstreamDriftCollector,
    )

    return {'upstream_drift': UpstreamDriftCollector().execute()}


@shared_task(name='self_improvement.scan_code_weekly')
def scan_code_weekly() -> dict:
    from core.self_improvement.collectors.code_quality import (  # noqa: PLC0415
        CodeQualityCollector,
    )

    return {'code_quality': CodeQualityCollector().execute()}


@shared_task(name='self_improvement.analyze_nightly')
def analyze_nightly(window_hours: int = 24) -> dict:
    """Plan-and-execute analyzer pipeline run."""
    from core.self_improvement.recommend import run_analyzer  # noqa: PLC0415

    return run_analyzer(window_hours=window_hours)


@shared_task(name='self_improvement.execute_queue')
def execute_queue() -> dict:
    """Phase 2: pick up approved + auto-applied recommendations and
    dispatch to the registered Healer. Runs every 5 minutes."""
    from core.self_improvement.heal import execute_queue as _run  # noqa: PLC0415

    return _run()


@shared_task(name='self_improvement.digest_weekly')
def digest_weekly() -> dict:
    """Generate + email the weekly engineering digest."""
    from datetime import timedelta  # noqa: PLC0415

    from django.utils import timezone  # noqa: PLC0415

    from core.self_improvement.models import SiActionLog, SiRecommendation  # noqa: PLC0415

    since = timezone.now() - timedelta(days=7)
    accepted = SiRecommendation.objects.filter(
        created_at__gte=since, status__in=('approved', 'auto_applied', 'merged')
    ).count()
    rejected = SiRecommendation.objects.filter(
        created_at__gte=since, status__in=('rejected', 'suppressed')
    ).count()
    rollbacks = SiActionLog.objects.filter(
        created_at__gte=since, phase='rollback', outcome='ok'
    ).count()
    total = accepted + rejected
    rollback_rate = rollbacks / total if total else 0.0

    logger.info(
        'self_improvement digest: accepted=%s rejected=%s rollbacks=%s',
        accepted,
        rejected,
        rollbacks,
    )
    return {
        'accepted': accepted,
        'rejected': rejected,
        'rollbacks': rollbacks,
        'rollback_rate': rollback_rate,
    }


def register_beat_schedule(schedule: dict) -> None:
    """Called from morph/celery.py after app.conf.beat_schedule is set.

    Adds the engine's entries via setdefault so a merchant can override
    by writing their own keys before importing this module.
    """
    from celery.schedules import crontab  # noqa: PLC0415

    schedule.setdefault(
        'self_improvement.ingest_hourly',
        {'task': 'self_improvement.ingest_hourly', 'schedule': crontab(minute=7)},
    )
    schedule.setdefault(
        'self_improvement.scan_seo_daily',
        {
            'task': 'self_improvement.scan_seo_daily',
            'schedule': crontab(hour=3, minute=30),
        },
    )
    schedule.setdefault(
        'self_improvement.scan_drift_daily',
        {
            'task': 'self_improvement.scan_drift_daily',
            'schedule': crontab(hour=4, minute=30),
        },
    )
    schedule.setdefault(
        'self_improvement.analyze_nightly',
        {
            'task': 'self_improvement.analyze_nightly',
            'schedule': crontab(hour=4, minute=0),
        },
    )
    schedule.setdefault(
        'self_improvement.scan_code_weekly',
        {
            'task': 'self_improvement.scan_code_weekly',
            'schedule': crontab(hour=5, minute=0, day_of_week=1),
        },
    )
    schedule.setdefault(
        'self_improvement.digest_weekly',
        {
            'task': 'self_improvement.digest_weekly',
            'schedule': crontab(hour=9, minute=0, day_of_week=1),
        },
    )
    schedule.setdefault(
        'self_improvement.execute_queue',
        {
            'task': 'self_improvement.execute_queue',
            'schedule': crontab(minute='*/5'),
        },
    )

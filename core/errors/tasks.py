"""Celery tasks for core.errors.

Scheduled from [`morph/celery.py`](../../morph/celery.py) — kept in this
module so autodiscover_tasks finds it without extra wiring.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger('morpheus.errors')


@shared_task(name='core.errors.tasks.prune_errors_task', ignore_result=True)
def prune_errors_task(keep_days: int = 30) -> int:
    """Daily prune wrapper around the management command logic.

    Returns the number of rows deleted. Logged but not raised on failure
    — the task should not crash worker if the table is briefly unreachable.
    """
    from datetime import timedelta

    from django.utils import timezone

    from core.errors.models import ErrorEvent

    cutoff = timezone.now() - timedelta(days=keep_days)
    qs = ErrorEvent.objects.filter(created_at__lt=cutoff)
    deleted, _ = qs.delete()
    logger.info(
        'prune_errors_task: deleted=%s cutoff=%s keep_days=%s',
        deleted,
        cutoff.isoformat(),
        keep_days,
    )
    return deleted


@shared_task(name='core.errors.tasks.error_digest_task', ignore_result=True)
def error_digest_task(hours: int = 24) -> int:
    """Email the operator the day's server errors, grouped (nothing on a clean day)."""
    from core.errors.alerts import send_digest

    return send_digest(hours)


@shared_task(name='core.errors.tasks.nightly_health_check', ignore_result=True)
def nightly_health_check() -> int:
    """Run the health checks; failures are logged and emailed. Returns the failure count."""
    from core.errors.health import run_and_report

    return len(run_and_report())

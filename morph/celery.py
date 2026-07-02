"""
Morpheus CMS — Celery Configuration.

Wires the Celery app to Django settings, hooks OpenTelemetry + Sentry, and
captures every task failure into the observability ErrorEvent table so the
merchant dashboard can see them.
"""

# ruff: noqa: PLC0415, S110
# Inline imports are intentional in this file — observability + plugins
# may not be importable at Celery bootstrap time; the defensive
# try/except/pass blocks keep boot resilient.

from __future__ import annotations

import logging
import os

from celery import Celery
from celery.signals import task_failure

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'morph.settings')

logger = logging.getLogger('morpheus.celery')

app = Celery('morpheus')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# ── Beat schedule ────────────────────────────────────────────────────────────
# Long-running periodic jobs live here so the merchant doesn't need to set up
# cron entries in Coolify. Each entry runs on the `beat` container.
from celery.schedules import crontab  # noqa: E402

app.conf.beat_schedule = {
    # Prune the error log nightly so the table stays bounded on noisy
    # storefronts. 30-day retention; older rows are deleted.
    'core-errors-prune': {
        'task': 'core.errors.tasks.prune_errors_task',
        'schedule': crontab(hour=3, minute=15),  # 03:15 UTC daily
    },
    # Check upstream for a new Morpheus version once a day; caches the result
    # so the dashboard can flag "update available" without a per-request fetch.
    'core-check-for-updates': {
        'task': 'core.tasks.check_for_updates',
        'schedule': crontab(hour=4, minute=45),  # 04:45 UTC daily
    },
    # Drain the transactional outbox into NATS JetStream every minute. Events are
    # written to OutboxEvent in the SAME DB transaction as the domain mutation
    # (core/hooks.py), and this is the ONLY path that publishes them. The task
    # existed but was scheduled nowhere, so events accumulated undelivered and the
    # at-least-once guarantee was broken; this restores it (and bounds the table).
    'core-outbox-publish': {
        'task': 'core.tasks.process_outbox',
        'schedule': crontab(minute='*'),  # every minute
    },
}

# Self-improvement engine — registers ingest/analyze/digest tasks.
try:
    from core.self_improvement.tasks import register_beat_schedule as _si_register

    _si_register(app.conf.beat_schedule)
except Exception:  # noqa: BLE001 — beat boot must not fail on engine import error
    pass

# Observability bootstrap — fail-soft: missing OTel deps must not break workers.
try:
    from core.observability import init_observability

    init_observability()
except Exception as e:  # noqa: BLE001
    logger.debug('celery: observability init skipped: %s', e)

try:
    from core.sentry import init_sentry

    init_sentry()
except Exception as e:  # noqa: BLE001
    logger.debug('celery: sentry init skipped: %s', e)


@task_failure.connect
def _on_task_failure(
    sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwargs
):
    """Persist task failures into the ErrorEvent table + Redis deadletter."""
    msg = str(exception)[:5000]
    stack = (str(einfo) if einfo else '')[:20000]
    try:
        from plugins.installed.observability.services import record_error

        record_error(
            source='celery',
            message=msg,
            stack_trace=stack,
            metadata={
                'task': sender.name if sender else '',
                'task_id': task_id or '',
                'exc_type': type(exception).__name__ if exception else '',
            },
        )
    except Exception as e:  # noqa: BLE001 — observability outage must not block worker
        logger.debug('celery: failed to record_error: %s', e)

    try:
        from django.core.cache import cache

        cache.set(
            f'morpheus:deadletter:{task_id}',
            {'task': sender.name if sender else '', 'message': msg, 'stack': stack[:2000]},
            timeout=60 * 60 * 24 * 7,
        )
    except Exception as e:  # noqa: BLE001 — cache outage must not block worker
        logger.debug('celery: failed to write deadletter: %s', e)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

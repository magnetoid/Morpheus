"""Feature-adoption background tasks."""

from __future__ import annotations

import logging

from morph.celery import app

logger = logging.getLogger('morpheus.feature_adoption')


@app.task(
    name='feature_adoption.flush_usage_counters',
    ignore_result=True,
    time_limit=60,
    soft_time_limit=30,
)
def flush_usage_counters() -> int:
    """Hourly: drain cache usage counters into ``FeatureUsageDay``."""
    from plugins.installed.feature_adoption.tracking import flush_counters

    try:
        return flush_counters()
    except Exception as exc:  # noqa: BLE001 — a beat task must never crash the scheduler
        logger.warning('feature_adoption: flush failed: %s', exc, exc_info=True)
        return 0

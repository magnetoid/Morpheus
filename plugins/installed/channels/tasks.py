"""Channels background task — refresh the cached cross-channel ads KPIs.

Runs the CHANNELS_METRICS filter (live ads-report calls across every connected
channel) once a day and caches the aggregated rows so the overview page can show
performance KPIs without making API calls on page load."""

from __future__ import annotations

import logging

from morph.celery import app

logger = logging.getLogger('morpheus.channels')

METRICS_CACHE_KEY = 'channels:metrics:v1'
_TTL = 60 * 60 * 26  # survives until the next daily run


@app.task(name='channels.refresh_metrics', ignore_result=True, time_limit=300, soft_time_limit=270)
def refresh_metrics():
    try:
        from django.core.cache import cache

        from core.hooks import MorpheusEvents, hook_registry

        rows = hook_registry.filter(MorpheusEvents.CHANNELS_METRICS, value=[]) or []
        rows = [r for r in rows if isinstance(r, dict) and r.get('name')]
        cache.set(METRICS_CACHE_KEY, rows, _TTL)
        return {'channels': len(rows)}
    except Exception as e:  # noqa: BLE001
        logger.warning('channels: refresh_metrics failed: %s', e)
        return {'ok': False, 'reason': str(e)[:200]}

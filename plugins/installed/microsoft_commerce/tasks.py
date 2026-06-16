"""Microsoft Commerce background tasks (placeholder for scheduled feed work)."""

from __future__ import annotations

import logging

from morph.celery import app

logger = logging.getLogger('morpheus.microsoft_commerce')


@app.task(
    name='microsoft_commerce.rebuild_feed', ignore_result=True, time_limit=600, soft_time_limit=540
)
def rebuild_feed():
    """Rebuild + cache the catalog feed (Microsoft pulls the feed URL on a schedule;
    this keeps our cache warm)."""
    try:
        from django.core.cache import cache

        from plugins.installed.microsoft_commerce.services.feed import build_feed
        from plugins.installed.microsoft_commerce.views import FEED_CACHE_KEY

        xml, stats = build_feed()
        cache.set(FEED_CACHE_KEY, xml, 60 * 60)
        return stats
    except Exception as e:  # noqa: BLE001
        logger.warning('microsoft_commerce: rebuild_feed task failed: %s', e)
        return {'ok': False, 'reason': str(e)[:200]}


@app.task(
    name='microsoft_commerce.fetch_ads_report',
    ignore_result=True,
    time_limit=120,
    soft_time_limit=110,
)
def fetch_ads_report(days=30):
    """Run the async Microsoft Ads report and cache it (the dashboard reads the
    cache; this keeps the report fetch off the request path)."""
    try:
        from plugins.installed.microsoft_commerce.services.reporting import fetch_and_cache

        return fetch_and_cache(days=int(days or 30))
    except Exception as e:  # noqa: BLE001
        logger.warning('microsoft_commerce: fetch_ads_report task failed: %s', e)
        return {'ok': False, 'reason': str(e)[:200]}

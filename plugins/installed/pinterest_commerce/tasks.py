"""Pinterest Commerce background tasks (placeholder for scheduled feed work)."""

from __future__ import annotations

import logging

from morph.celery import app

logger = logging.getLogger('morpheus.pinterest_commerce')


@app.task(
    name='pinterest_commerce.rebuild_feed', ignore_result=True, time_limit=600, soft_time_limit=540
)
def rebuild_feed():
    """Rebuild + cache the catalog feed (Pinterest pulls the feed URL on a schedule;
    this keeps our cache warm)."""
    try:
        from django.core.cache import cache

        from plugins.installed.pinterest_commerce.services.feed import build_feed
        from plugins.installed.pinterest_commerce.views import FEED_CACHE_KEY

        xml, stats = build_feed()
        cache.set(FEED_CACHE_KEY, xml, 60 * 60)
        return stats
    except Exception as e:  # noqa: BLE001
        logger.warning('pinterest_commerce: rebuild_feed task failed: %s', e)
        return {'ok': False, 'reason': str(e)[:200]}

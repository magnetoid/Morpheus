"""Amazon Ads background tasks."""

from __future__ import annotations

import logging

from morph.celery import app

logger = logging.getLogger('morpheus.amazon_ads')


@app.task(name='amazon_ads.fetch_report', ignore_result=True, time_limit=120, soft_time_limit=110)
def fetch_report(days=30):
    """Run the async Amazon Ads report and cache it (off the request path)."""
    try:
        from plugins.installed.amazon_ads.services.reporting import fetch_and_cache

        return fetch_and_cache(days=int(days or 30))
    except Exception as e:  # noqa: BLE001
        logger.warning('amazon_ads: fetch_report task failed: %s', e)
        return {'ok': False, 'reason': str(e)[:200]}

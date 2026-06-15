"""Google Shopping background tasks."""

from __future__ import annotations

import logging

from morph.celery import app

logger = logging.getLogger('morpheus.google_shopping')


@app.task(
    name='google_shopping.push_content_api', ignore_result=True, time_limit=600, soft_time_limit=540
)
def push_content_api():
    """Periodic Content API push — no-op when the plugin isn't connected."""
    try:
        from plugins.installed.google_shopping.services.content_api import push_products

        stats = push_products()
        if stats.get('ok') and stats.get('sent'):
            logger.info('google_shopping: content push sent %s products', stats['sent'])
        return stats
    except Exception as e:  # noqa: BLE001 — a beat task must never crash the worker
        logger.warning('google_shopping: content push task failed: %s', e)
        return {'ok': False, 'reason': str(e)[:200]}

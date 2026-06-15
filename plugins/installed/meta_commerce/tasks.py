"""Meta Commerce background tasks."""

from __future__ import annotations

import logging

from morph.celery import app

logger = logging.getLogger('morpheus.meta_commerce')


@app.task(
    name='meta_commerce.push_catalog', ignore_result=True, time_limit=600, soft_time_limit=540
)
def push_catalog():
    """Periodic Catalog API push — no-op until connected."""
    try:
        from plugins.installed.meta_commerce.services.catalog_api import push_products

        stats = push_products()
        if stats.get('ok') and stats.get('sent'):
            logger.info('meta_commerce: catalog push sent %s items', stats['sent'])
        return stats
    except Exception as e:  # noqa: BLE001
        logger.warning('meta_commerce: catalog push task failed: %s', e)
        return {'ok': False, 'reason': str(e)[:200]}

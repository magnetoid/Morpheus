"""customers — nightly RFM recompute."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger('morpheus.customers')


@shared_task(name='customers.recompute_rfm')
def recompute_rfm() -> dict:
    """Rescore every customer's RFM segment. Fires CUSTOMER_SEGMENT_CHANGED on flips."""
    from plugins.installed.customers.rfm import recompute_all

    result = recompute_all()
    logger.info('customers.recompute_rfm: %s', result)
    return result

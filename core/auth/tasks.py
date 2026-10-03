"""Celery tasks for core.auth.

Scheduled from [`morph/celery.py`](../../morph/celery.py) — kept in this
module so autodiscover_tasks finds it without extra wiring.
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger('morpheus.core.auth')


@shared_task(name='core.auth.tasks.prune_sign_ins_task', ignore_result=True)
def prune_sign_ins_task() -> int:
    """Daily: drop sign-in log entries past their retention (IPs are personal data)."""
    from core.auth.sign_ins import KEEP_DAYS, prune_sign_ins

    deleted = prune_sign_ins()
    logger.info('prune_sign_ins_task: deleted=%s keep_days=%s', deleted, KEEP_DAYS)
    return deleted

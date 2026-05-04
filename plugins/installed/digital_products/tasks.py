"""digital_products plugin — Celery tasks."""
from __future__ import annotations

import logging
from celery import shared_task

logger = logging.getLogger("morpheus.digital_products")


@shared_task(bind=True, time_limit=60, soft_time_limit=45)
def example_task(self, payload: dict) -> None:
    logger.info("example_task received payload=%s", payload)

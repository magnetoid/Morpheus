"""Storefront async tasks."""

from __future__ import annotations

import logging

from celery import shared_task

from morph.celery import app  # noqa: F401 — registers app on import

logger = logging.getLogger('morpheus.storefront.tasks')


@shared_task
def send_order_confirmation(order_id: str) -> bool:
    """Async wrapper around ``orders.email.send_order_confirmation``.

    Hooks fire synchronously inside the request — pushing email send to
    Celery keeps order placement snappy. Falls through cleanly when the
    order is gone (race) or the email helper isn't installed.
    """
    try:
        from plugins.installed.orders.email import (
            send_order_confirmation as _send,
        )
        from plugins.installed.orders.models import Order
    except Exception as e:  # noqa: BLE001
        logger.warning('storefront.send_order_confirmation: deps missing: %s', e)
        return False
    order = Order.objects.filter(pk=order_id).first()
    if order is None:
        logger.info('storefront.send_order_confirmation: order %s not found', order_id)
        return False
    try:
        return bool(_send(order))
    except Exception as e:  # noqa: BLE001 — never crash the worker on a single email
        logger.warning('storefront.send_order_confirmation: send failed: %s', e)
        return False

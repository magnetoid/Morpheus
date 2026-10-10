"""CJ background work: send one order, and the 20-minute sweep."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger('morpheus.cjdropshipping')


@shared_task(name='cjdropshipping.forward', time_limit=180, soft_time_limit=150)
def forward(order_id: str) -> str:
    from plugins.installed.cjdropshipping.services.client import CJError
    from plugins.installed.cjdropshipping.services.orders import forward_order, lines_for
    from plugins.installed.orders.models import Order

    order = Order.objects.filter(pk=order_id).first()
    if order is None or not lines_for(order)[0]:
        return 'no CJ lines'
    try:
        record = forward_order(order)
    except CJError as e:
        return f'failed: {e.message}'
    return record.status if record else 'already sent'


@shared_task(name='cjdropshipping.sync', time_limit=900, soft_time_limit=840)
def sync() -> dict:
    """Send what the ORDER_PAID hook missed, then refresh every open CJ order."""
    from plugins.installed.cjdropshipping.services.client import CJError, api_key, config
    from plugins.installed.cjdropshipping.services.orders import (
        forward_order,
        orders_to_send,
        sync_open_orders,
    )

    if not api_key():
        return {'skipped': 'no API key'}
    sent = 0
    try:
        if config().get('auto_forward', True):
            for order in orders_to_send()[:25]:
                if forward_order(order) is not None:
                    sent += 1
        read = sync_open_orders()
    except CJError as e:
        logger.warning('cjdropshipping: sync stopped: %s', e.message)
        return {'sent': sent, 'error': e.message}
    return {'sent': sent, 'read': read}

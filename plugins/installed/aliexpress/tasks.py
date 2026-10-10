"""AliExpress background work: place one order, and the 30-minute sweep."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger('morpheus.aliexpress')


@shared_task(name='aliexpress.forward', time_limit=180, soft_time_limit=150)
def forward(order_id: str) -> str:
    from plugins.installed.aliexpress.services.client import AEError
    from plugins.installed.aliexpress.services.orders import forward_order, lines_for
    from plugins.installed.orders.models import Order

    order = Order.objects.filter(pk=order_id).first()
    if order is None or not lines_for(order)[0]:
        return 'no AliExpress lines'
    try:
        record = forward_order(order)
    except AEError as e:
        return f'failed: {e.message}'
    return record.status if record else 'already placed'


@shared_task(name='aliexpress.sync', time_limit=900, soft_time_limit=840)
def sync() -> dict:
    """Keep the token fresh, place what the hook missed, read every open order."""
    from plugins.installed.aliexpress.services.client import (
        AEError,
        access_token,
        config,
        connection,
    )
    from plugins.installed.aliexpress.services.orders import (
        forward_order,
        orders_to_send,
        sync_open_orders,
    )

    if not connection()['connected']:
        return {'skipped': 'not connected'}
    placed = 0
    try:
        access_token()  # refreshes when under two days are left
        if config().get('auto_forward', True):
            for order in orders_to_send()[:25]:
                if forward_order(order) is not None:
                    placed += 1
        read = sync_open_orders()
    except AEError as e:
        logger.warning('aliexpress: sync stopped: %s', e.message)
        return {'placed': placed, 'error': e.message}
    return {'placed': placed, 'read': read}

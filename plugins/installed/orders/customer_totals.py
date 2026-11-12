"""What a customer bought, kept on their contact (v0.157.0).

A contact's purchase count, lifetime value and last order (customers' columns,
read by the Contacts list's sort, the RFM segments and Linda's customer tools)
are this app's sales rule (``reports``) for that customer. They used to be
raised by each paid order's full total and never lowered: a refund, a
cancellation after payment and a cash-on-delivery order not yet paid all left
them wrong.

Each order event refreshes its customer once the transaction commits. A
cancellation's event fires before its caller saves the order, so it waits for
the save (``on_order_saved``); the
nightly job refreshes everyone, so a write that skipped the events (a
``QuerySet.update()``) heals by the next morning.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import DatabaseError, transaction

logger = logging.getLogger('morpheus.orders')

_ZERO = Decimal('0.00')


def refresh(customer_ids) -> int:
    """Write each listed customer's totals from the sales rule. Returns how many."""
    from plugins.installed.customers.services import set_cdp_metrics  # noqa: PLC0415
    from plugins.installed.orders.reports import by_customer  # noqa: PLC0415

    ids = [pk for pk in customer_ids if pk]
    if not ids:
        return 0
    totals = by_customer(ids)
    for pk in ids:
        sales = totals.get(str(pk))
        set_cdp_metrics(
            pk,
            purchase_count=sales.orders if sales else 0,
            lifetime_value=sales.net if sales else _ZERO,
            last_order_at=sales.last_order_at if sales else None,
        )
    return len(ids)


def refresh_all() -> int:
    """Every customer with an order, or with totals that no longer have one."""
    from django.contrib.auth import get_user_model  # noqa: PLC0415

    from plugins.installed.orders.models import Order  # noqa: PLC0415

    ids = set(
        Order.objects.filter(customer__isnull=False).values_list('customer_id', flat=True)
    ) | set(get_user_model().objects.filter(purchase_count__gt=0).values_list('pk', flat=True))
    return refresh(sorted(ids))


def _refresh_soon(customer_id) -> None:
    def run():
        try:
            with transaction.atomic():
                refresh([customer_id])
        except DatabaseError:
            logger.warning(
                'orders: customer totals for %s not refreshed', customer_id, exc_info=True
            )

    transaction.on_commit(run)


def on_order_cancelled(order=None, **kwargs) -> None:
    """ORDER_CANCELLED fires from the FSM transition, before the caller's
    ``save()``: outside a transaction the refresh would read the row still
    uncancelled. Mark the order; ``on_order_saved`` refreshes once it is stored.
    An order already stored as cancelled (the event fired after an update) is
    refreshed now."""
    customer_id = getattr(order, 'customer_id', None)
    if not customer_id:
        return
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    if Order.objects.filter(pk=order.pk, status='cancelled').exists():
        _refresh_soon(customer_id)
    else:
        order._totals_after_save = True


def on_order_saved(sender, instance, **kwargs) -> None:
    """post_save of an Order marked by ``on_order_cancelled``: refresh once."""
    if getattr(instance, '_totals_after_save', False):
        instance._totals_after_save = False
        _refresh_soon(instance.customer_id)


def on_order_changed(order=None, **kwargs) -> None:
    """ORDER_PLACED, ORDER_PAID and PAYMENT_REFUNDED: the
    order's customer bought something else now."""
    customer_id = getattr(order, 'customer_id', None)
    if customer_id:
        _refresh_soon(customer_id)

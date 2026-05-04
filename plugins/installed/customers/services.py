"""Customer-side business logic.

`update_cdp_metrics` is the canonical writer for Customer.lifetime_value /
.purchase_count / .last_order_at — kept in one place so the dashboard,
ORDER_PAID hook, and any backfill script all agree on what "LTV" means.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger('morpheus.customers.cdp')


def update_cdp_metrics(order) -> None:
    """Bump the contact's CDP rollups for a freshly-paid order.

    Uses ``F()`` increments so concurrent ORDER_PAID hooks for the same
    customer don't trample each other. Idempotency is the caller's job —
    we expect ORDER_PAID to fire once per state transition.
    """
    customer = getattr(order, 'customer', None)
    if customer is None or not customer.pk:
        return
    total_amount = getattr(order, 'total', None)
    if hasattr(total_amount, 'amount'):
        total_amount = total_amount.amount
    if total_amount is None:
        return
    try:
        total_amount = Decimal(str(total_amount))
    except Exception:  # noqa: BLE001
        logger.debug('customers.cdp: non-decimal total on order %s', getattr(order, 'pk', '?'))
        return

    placed_at = getattr(order, 'created_at', None) or timezone.now()
    Customer = customer.__class__
    with transaction.atomic():
        (Customer.objects
            .filter(pk=customer.pk)
            .update(
                lifetime_value=F('lifetime_value') + total_amount,
                purchase_count=F('purchase_count') + 1,
                last_order_at=placed_at,
            ))

"""Loyalty-points service layer + ORDER_PAID handler registration."""

# ruff: noqa: PLC0415, I001
# Inline imports are intentional — avoid app-registry-not-ready issues
# when this module is imported from apps.py:ready() before all models
# are loaded.
from __future__ import annotations

import logging
from decimal import Decimal

logger = logging.getLogger('morpheus.loyalty')


def get_balance(customer) -> int:
    """Sum of ``points`` for a customer's transactions. Zero for guests."""
    if customer is None or not getattr(customer, 'is_authenticated', False):
        return 0
    from django.db.models import Sum
    from plugins.installed.loyalty_points.models import PointsTransaction

    total = PointsTransaction.objects.filter(customer=customer).aggregate(total=Sum('points'))[
        'total'
    ]
    return int(total or 0)


def award_points(
    customer, points: int, *, reason: str = 'earn_order', order_number: str = '', note: str = ''
):
    """Idempotent earn for a (customer, order_number) pair when reason='earn_order'."""
    if customer is None or points == 0:
        return None
    from plugins.installed.loyalty_points.models import PointsTransaction

    if reason == 'earn_order' and order_number:
        existing = PointsTransaction.objects.filter(
            customer=customer,
            reason=reason,
            order_number=order_number,
        ).first()
        if existing is not None:
            return existing
    return PointsTransaction.objects.create(
        customer=customer,
        points=points,
        reason=reason,
        order_number=order_number or '',
        note=note or '',
    )


def _on_order_paid(order=None, **_kwargs):
    """ORDER_PAID handler — award 1 point per currency unit, rounded down.

    Order may have a guest customer (no User row). In that case we skip
    silently — points require an account to redeem against later.
    """
    if order is None:
        return
    customer = getattr(order, 'customer', None) or getattr(order, 'user', None)
    if customer is None or not getattr(customer, 'is_authenticated', True):
        return
    total_money = getattr(order, 'total', None) or getattr(order, 'grand_total', None)
    amount = getattr(total_money, 'amount', total_money)
    try:
        points = int(Decimal(str(amount or 0)))
    except Exception:  # noqa: BLE001
        return
    if points <= 0:
        return
    try:
        award_points(
            customer,
            points,
            reason='earn_order',
            order_number=str(
                getattr(order, 'number', '') or getattr(order, 'order_number', '') or order.pk
            ),
            note=f'+{points} pts on paid order',
        )
    except Exception as e:  # noqa: BLE001 — never let loyalty break a paid order
        logger.warning('loyalty: award_points failed: %s', e)


def register_handlers() -> None:
    from core.hooks import hook_registry, MorpheusEvents

    hook_registry.register(MorpheusEvents.ORDER_PAID, _on_order_paid, priority=80)

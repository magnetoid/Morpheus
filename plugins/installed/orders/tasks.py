"""Order background tasks.

**Stranded reservations.** Checkout reserves stock through the fail-closed
``ORDER_RESERVE_STOCK`` gate, and the reservation is released on
``ORDER_CANCELLED`` (inventory subscribes it). But nothing ever cancelled an
order that was created and then never paid: a failed card only marks the
transaction FAILED (payments/services/stripe.py), and an abandoned redirect
leaves the order sitting ``pending`` + unpaid forever. Its units stayed reserved
for good, so `_available()` shrank with every abandoned checkout until the
merchant looked oversold on stock they still had.

This expires those orders, which fires ``ORDER_CANCELLED`` and lets the existing
subscribers do the rest — releasing the DB reservation and restoring any
gift-card / loyalty tender.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('morpheus.orders')

#: Conservative default. Long enough for a slow 3-D Secure challenge or a
#: shopper who tabs away mid-payment, short enough that a burst of abandoned
#: checkouts doesn't hold a small merchant's stock hostage for a day.
DEFAULT_EXPIRY_MINUTES = 60

#: Gateways whose orders are paid later by design — on delivery, or by a bank
#: transfer the merchant reconciles by hand. The sweep is for abandoned card
#: checkouts; it used to cancel every cash-on-delivery order after an hour on a
#: store whose only payment method was cash on delivery.
OFFLINE_GATEWAYS = ('cod', 'manual')


def _expiry_minutes() -> int:
    """Merchant knob, read fresh (a plugin config cache is per-process)."""
    try:
        from plugins.registry import app_registry

        plugin = app_registry.get('orders')
        raw = plugin.get_config_value('pending_order_expiry_minutes', DEFAULT_EXPIRY_MINUTES)
        return max(0, int(raw))
    except Exception:  # noqa: BLE001 — a config problem must not stop the sweep
        return DEFAULT_EXPIRY_MINUTES


@shared_task(name='orders.expire_pending_orders')
def expire_pending_orders() -> int:
    """Cancel unpaid orders left ``pending`` past the expiry window.

    Returns the number cancelled. ``0`` minutes disables the sweep entirely
    (the guardrails convention), for merchants who reconcile by hand.

    Each order is cancelled in its own transaction so one bad row cannot abort
    the batch, and a paid-in-the-meantime order is re-checked under a row lock
    before cancelling — the window between selecting and cancelling is exactly
    where a late webhook lands, and cancelling a paid order would be far worse
    than leaving one stranded.
    """
    from plugins.installed.orders.models import Order

    minutes = _expiry_minutes()
    if minutes <= 0:
        return 0

    cutoff = timezone.now() - timezone.timedelta(minutes=minutes)
    candidates = list(
        Order.objects.filter(status='pending', placed_at__lt=cutoff)
        .exclude(payment_status='paid')
        .exclude(payment_gateway__in=OFFLINE_GATEWAYS)
        .values_list('id', flat=True)[:500]
    )

    cancelled = 0
    for order_id in candidates:
        try:
            with transaction.atomic():
                order = Order.objects.select_for_update().get(pk=order_id)
                if order.status != 'pending' or order.payment_status == 'paid':
                    continue  # paid or advanced between select and lock
                order.cancel(reason=f'Unpaid for over {minutes} minutes — expired automatically.')
                order.save(update_fields=['status', 'cancelled_at', 'staff_notes'])
            cancelled += 1
        except Exception:  # noqa: BLE001 — one bad order must not stop the sweep
            logger.warning('orders: failed to expire order %s', order_id, exc_info=True)

    if cancelled:
        logger.info('orders: expired %s unpaid pending order(s) older than %sm', cancelled, minutes)
    return cancelled

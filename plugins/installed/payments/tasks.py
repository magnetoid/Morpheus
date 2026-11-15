"""Payments' background jobs: taking or releasing a held card payment.

They live here because the Celery worker imports only each app's ``tasks``
module: a task defined anywhere else never reaches it.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('morpheus.payments.tasks')


@shared_task(name='payments.capture_held_payment')
def capture_held_payment(order_id: str) -> bool:
    """Charge the order's held payment (a parcel shipped, by capture_mode)."""
    from plugins.installed.orders.models import Order  # noqa: PLC0415
    from plugins.installed.payments.services.capture import capture_order  # noqa: PLC0415

    order = Order.objects.filter(pk=order_id).first()
    if order is None:
        return False
    return bool(capture_order(order).get('success'))


@shared_task(name='payments.release_held_payment')
def release_held_payment(order_id: str, reason: str = '', tx_id: str = '') -> bool:
    """Give back a held payment: ``tx_id``'s, else the order's (the order was
    cancelled, or a second payment attempt was confirmed). A release that fails
    is tried again by the hourly sweep while the order is closed or paid."""
    from plugins.installed.orders.models import Order  # noqa: PLC0415
    from plugins.installed.payments.models import PaymentTransaction  # noqa: PLC0415
    from plugins.installed.payments.services.capture import (  # noqa: PLC0415
        release_order,
        release_transaction,
    )

    if tx_id:
        tx = PaymentTransaction.objects.filter(
            pk=tx_id, status=PaymentTransaction.Status.AUTHORIZED
        ).first()
        return bool(tx and release_transaction(tx, reason=reason).get('success'))
    order = Order.objects.filter(pk=order_id).first()
    if order is None:
        return False
    return bool(release_order(order, reason=reason).get('success'))


@shared_task(name='payments.release_stale_authorizations')
def release_stale_authorizations() -> int:
    """Act on holds before the card network drops them, every hour.

    A hold older than ``authorization_days`` is charged
    (``authorization_expiry`` = capture, the default) or given back (release).
    A hold that must never be charged (its order cancelled or refunded, or paid
    by another payment) is given back whatever its age, so a release that
    failed is tried again. Returns how many were handled."""
    from django.db.models import Q  # noqa: PLC0415

    from plugins.installed.payments.models import PaymentTransaction  # noqa: PLC0415
    from plugins.installed.payments.services.capture import (  # noqa: PLC0415
        CLOSED_STATUSES,
        PAID_STATUSES,
        authorization_days,
        capture_order,
        expiry_action,
        release_transaction,
        surplus_reason,
    )

    cutoff = timezone.now() - timezone.timedelta(days=authorization_days())
    stale = (
        PaymentTransaction.objects.filter(status=PaymentTransaction.Status.AUTHORIZED)
        .filter(
            Q(authorized_at__lt=cutoff)
            | Q(order__status__in=CLOSED_STATUSES)
            | Q(order__payment_status__in=PAID_STATUSES)
        )
        .select_related('order')
        .order_by('authorized_at')[:200]
    )
    action = expiry_action()
    done = 0
    for tx in stale:
        try:
            surplus = surplus_reason(tx.order, tx)
            if surplus or action == 'release':
                result = release_transaction(
                    tx,
                    reason=surplus or 'The hold reached its time limit, so it was released',
                )
            else:
                result = capture_order(tx.order)
            done += bool(result.get('success'))
        except Exception:  # noqa: BLE001 — one order must not stop the sweep
            logger.warning(
                'payments: could not settle hold on order %s', tx.order_id, exc_info=True
            )
    return done


#: Set on the order once the "try again" email has gone, so it goes once.
FAILED_EMAIL_KEY = 'failed_payment_email_at'


@shared_task(name='payments.send_failed_payment_email')
def send_failed_payment_email(order_id: str) -> bool:
    """Email the customer a link to pay after a declined card (the
    failed_payment_email_minutes setting): once per order, and only while the
    order is still open and unpaid."""
    from django.db import transaction  # noqa: PLC0415

    from plugins.installed.orders.models import Order  # noqa: PLC0415
    from plugins.installed.payments import pay_link  # noqa: PLC0415

    with transaction.atomic():
        order = Order.objects.select_for_update().filter(pk=order_id).first()
        if order is None or pay_link.state(order) != 'payable':
            return False
        md = dict(order.metadata) if isinstance(order.metadata, dict) else {}
        if md.get(FAILED_EMAIL_KEY):
            return False
        md[FAILED_EMAIL_KEY] = timezone.now().isoformat()
        order.metadata = md
        order.save(update_fields=['metadata'])
        sent, reason = pay_link.send(order, kind='failed')
    if not sent:
        logger.info('payments: no try-again email for order %s: %s', order.order_number, reason)
    return sent

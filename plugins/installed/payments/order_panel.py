"""The order page's "Payment" panel (``ORDER_DETAIL_PANELS``): a card payment
that is held until the order ships, or until the merchant charges it."""

from __future__ import annotations

from typing import Any

WHEN = {
    'first_parcel': 'when the first parcel is recorded',
    'all_shipped': 'when the last parcel is recorded',
    'manual': 'when you charge it',
}


def order_panel(value, order=None, request=None, **_: Any):
    if order is None or not isinstance(value, list):
        return value
    from django.template.loader import render_to_string  # noqa: PLC0415
    from django.utils import timezone  # noqa: PLC0415

    from plugins.installed.payments.models import PaymentTransaction  # noqa: PLC0415
    from plugins.installed.payments.services.capture import (  # noqa: PLC0415
        authorization_days,
        expiry_action,
        stored_mode,
    )

    mode = stored_mode(order)
    status = PaymentTransaction.Status
    held = PaymentTransaction.objects.filter(order=order, authorized_at__isnull=False)
    # What the order's money is waiting on: a hold still open, else the one
    # charged, else the latest given back (a second attempt given back never
    # hides the hold that counts).
    tx = None
    for wanted in (status.AUTHORIZED, status.SUCCEEDED, status.RELEASED):
        tx = held.filter(status=wanted).order_by('-authorized_at').first()
        if tx is not None:
            break
    if mode == 'immediate' or tx is None or tx.authorized_at is None:
        return value  # charged at checkout: the order's own payment line says it all
    failure = (
        order.events.filter(event_type='PAYMENT_CAPTURE_FAILED', created_at__gte=tx.authorized_at)
        .order_by('-created_at')
        .first()
    )
    html = render_to_string(
        'payments/dashboard/order_payment_panel.html',
        {
            'order': order,
            'tx': tx,
            'held': tx.status == status.AUTHORIZED,
            'released': tx.status == status.RELEASED,
            'charged': tx.status == status.SUCCEEDED,
            'when': WHEN.get(mode, ''),
            'settle_by': tx.authorized_at + timezone.timedelta(days=authorization_days()),
            'settle_action': expiry_action(),
            'failure': failure,
        },
        request=request,
    )
    value.append({'label': 'Payment', 'html': html, 'priority': 20})
    return value

"""The payment link: ``/pay/<public_token>/`` and the emails that carry it (A8).

A customer pays an order that is already placed: a draft staff converted, an
order whose card was declined, a quote. The page (``views_pay.pay_order``) starts
the payment through the checkout's own routing, so every gateway behaves as it
does at checkout. Sending a link holds the order out of the unpaid-order sweep
until its deadline (``orders.payment_deadline``).
"""

from __future__ import annotations

import logging
from datetime import UTC

logger = logging.getLogger('morpheus.payments')

#: Order states a customer can still pay in.
OPEN_STATUSES = ('pending', 'confirmed', 'processing')
#: Payment states that mean nothing was taken or held: never paid, or a held
#: card that was given back while the order stayed open.
UNPAID = ('unpaid', 'released')

#: Email template per kind of link.
_EMAIL = {'link': 'payment_link', 'failed': 'payment_failed'}


def state(order) -> str:
    """``'payable'``, ``'paid'`` (paid, held or refunded), ``'nothing'`` (a total
    of zero) or ``'cancelled'`` (cancelled, refunded, or past the point of
    payment: shipped, delivered)."""
    if order.status in ('cancelled', 'refunded'):
        return 'cancelled'
    if (order.payment_status or 'unpaid') not in UNPAID:
        return 'paid'
    if order.status not in OPEN_STATUSES:
        return 'cancelled'
    if order.total.amount <= 0:
        return 'nothing'
    return 'payable'


def pay_path(order) -> str:
    return f'/pay/{order.public_token}/'


def pay_url(order) -> str:
    from core.utils.site import site_base_url  # noqa: PLC0415

    return f'{site_base_url().rstrip("/")}{pay_path(order)}'


def recipient(order) -> str:
    return (
        getattr(order, 'email', '') or getattr(getattr(order, 'customer', None), 'email', '') or ''
    )


def send(order, *, kind: str = 'link') -> tuple[bool, str]:
    """Email the customer a link to pay ``order``; ``(sent, reason)``.

    ``kind`` is ``'link'`` (staff sent it) or ``'failed'`` (after a declined
    card). Refuses an order that cannot be paid or has no email address. A sent
    link holds the order for payment and goes on its timeline."""
    from core.emails.handlers import send_templated_email  # noqa: PLC0415
    from plugins.installed.orders.payment_deadline import (  # noqa: PLC0415
        cancels_at,
        hold_for_payment,
    )

    current = state(order)
    if current == 'paid':
        return False, 'This order is already paid.'
    if current == 'nothing':
        return False, 'This order has nothing to pay.'
    if current != 'payable':
        return False, 'This order is closed, so it cannot be paid.'
    to = recipient(order)
    if not to:
        return False, 'This order has no email address to send the link to.'

    hold_for_payment(order, reason=kind)
    # The deadline the customer is told: only one the sweep will keep.
    deadline = cancels_at(order)
    subject = (
        f'Pay for order #{order.order_number}'
        if kind == 'link'
        else f"Your payment for order #{order.order_number} didn't go through"
    )
    send_templated_email(
        _EMAIL.get(kind, 'payment_link'),
        to=to,
        subject=subject,
        ctx={'order': order, 'pay_url': pay_url(order), 'pay_by': deadline},
    )
    when = (
        f' It can be paid until {deadline.astimezone(UTC):%Y-%m-%d %H:%M} UTC.' if deadline else ''
    )
    order.log_event('PAYMENT_LINK_SENT', message=f'Payment link emailed to {to}.{when}')
    return True, ''

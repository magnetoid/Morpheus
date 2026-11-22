"""The customer's return emails, and what happens to a charged exchange (C4, v0.188.0).

Four emails follow a return, each sent only to the order's email address and each
linking the return's status page by the order's token, so a guest can open it:
request received, approved (with the merchant's return instructions), rejected (with
the staff note) and closed. Every email goes after the change commits.

An exchange that costs something (``exchange_fee``) leaves its order unpaid: closing
the return emails the payment link, and the new edition ships once it is paid. When
the unpaid-order sweep cancels that order at its deadline, the return is refunded
instead, once, and noted on the return and both orders.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction

logger = logging.getLogger('morpheus.returns_portal')

#: A refund paid when an exchange order is cancelled unpaid, told apart from the
#: return's own refund by its note.
UNPAID_NOTE = 'RMA {rma} (exchange not paid)'


def status_url(rr) -> str:
    from django.urls import reverse  # noqa: PLC0415

    from core.utils.site import site_base_url  # noqa: PLC0415

    path = reverse('returns_portal:return_status', args=[rr.pk])
    return f'{site_base_url().rstrip("/")}{path}?token={rr.order.public_token}'


def _lines(rr) -> list[dict]:
    from plugins.installed.orders.models import OrderItem  # noqa: PLC0415

    items = {str(o.pk): o for o in OrderItem.objects.filter(order=rr.order)}
    return [
        {'item': items[str(e.get('order_item_id'))], 'quantity': e.get('quantity', 0)}
        for e in rr.items or []
        if str(e.get('order_item_id')) in items
    ]


def _send(key: str, rr, subject: str, **extra) -> None:
    from core.emails.handlers import send_templated_email  # noqa: PLC0415

    to = (rr.order.email or '').strip()
    if not to:
        return
    ctx = {'order': rr.order, 'rma': rr, 'lines': _lines(rr), 'status_url': status_url(rr)}
    ctx.update(extra)
    try:
        send_templated_email(key, to=to, subject=subject, ctx=ctx, tag=f'return:{rr.pk}:{key}')
    except Exception as e:  # noqa: BLE001 — an email never undoes a return
        logger.error('returns_portal: %s for %s failed: %s', key, rr.rma_number, e)


def _after_commit(fn) -> None:
    transaction.on_commit(fn)


def on_return_requested(return_request=None, **kwargs):
    rr = return_request
    # A withdrawal from the contract has its own receipt (withdrawal_received).
    if rr is None or rr.reason == 'withdrawal':
        return
    _after_commit(
        lambda: _send('return_requested', rr, f'We received your return request {rr.rma_number}')
    )


def on_return_approved(return_request=None, **kwargs):
    from plugins.installed.returns_portal.policy import return_instructions  # noqa: PLC0415

    rr = return_request
    if rr is None:
        return
    instructions = return_instructions()
    _after_commit(
        lambda: _send(
            'return_approved',
            rr,
            f'Your return {rr.rma_number} is approved',
            instructions=instructions,
        )
    )


def on_return_rejected(return_request=None, **kwargs):
    rr = return_request
    if rr is None:
        return
    _after_commit(lambda: _send('return_rejected', rr, f'About your return {rr.rma_number}'))


def _unmade_lines(rr, unmade) -> list[dict]:
    from plugins.installed.catalog.models import ProductVariant  # noqa: PLC0415

    items = {str(line['item'].pk): line['item'] for line in _lines(rr)}
    wanted = {
        str(v.pk): v
        for v in ProductVariant.objects.filter(
            pk__in=[u.get('variant_id') for u in unmade if u.get('variant_id')]
        )
    }
    return [
        {'item': items[str(u.get('order_item_id'))], 'wanted': wanted.get(str(u.get('variant_id')))}
        for u in unmade
        if str(u.get('order_item_id')) in items
    ]


def on_return_closed(
    return_request=None,
    refund=None,
    store_credit=None,
    outcome='refund',
    exchange_order=None,
    unmade=None,
    **kwargs,
):
    """``return.refunded``: the closing email, and the payment link when the
    exchange order still has something to pay."""
    from plugins.installed.returns_portal.policy import OUTCOME_LABELS  # noqa: PLC0415

    rr = return_request
    if rr is None:
        return
    owes = exchange_order is not None and exchange_order.total.amount > 0
    ctx = {
        'outcome': outcome,
        'outcome_label': OUTCOME_LABELS.get(outcome, outcome),
        'refund_amount': refund.amount if refund is not None else None,
        'credit_amount': store_credit,
        'exchange_order': exchange_order,
        'exchange_owes': owes,
        'unmade_lines': _unmade_lines(rr, unmade or []),
    }

    def send():
        _send('return_closed', rr, f'Your return {rr.rma_number} is closed', **ctx)
        if owes:
            from plugins.installed.payments import pay_link  # noqa: PLC0415

            sent, reason = pay_link.send(exchange_order, kind='link')
            if not sent:
                logger.warning(
                    'returns_portal: no payment link for exchange %s: %s',
                    exchange_order.order_number,
                    reason,
                )

    _after_commit(send)


def on_order_cancelled(order=None, **kwargs):
    """ORDER_CANCELLED: an exchange order cancelled before it was paid refunds its
    return instead, once the cancellation commits."""
    metadata = getattr(order, 'metadata', None) or {}
    if order is None or not metadata.get('exchange_of') or not metadata.get('return_id'):
        return
    pk, return_id = order.pk, metadata['return_id']
    _after_commit(lambda: refund_unpaid_exchange(pk, return_id))


def refund_unpaid_exchange(order_pk, return_id) -> None:
    from djmoney.money import Money  # noqa: PLC0415

    from plugins.installed.orders.models import Order  # noqa: PLC0415
    from plugins.installed.orders.refunds import (  # noqa: PLC0415
        RefundService,
        ReturnRequest,
        ReturnService,
    )
    from plugins.installed.payments.pay_link import UNPAID  # noqa: PLC0415
    from plugins.installed.returns_portal.policy import return_fee  # noqa: PLC0415

    exchange = Order.objects.filter(pk=order_pk).first()
    if exchange is None or exchange.status != 'cancelled':
        return
    if (exchange.payment_status or 'unpaid') not in UNPAID:
        return
    rr = ReturnRequest.objects.select_related('order', 'refund').filter(pk=return_id).first()
    if rr is None:
        return
    note = UNPAID_NOTE.format(rma=rr.rma_number)
    if rr.order.refunds.filter(notes=note).exists():
        return
    value = rr.refund_amount
    if value is None or value.amount <= 0:
        value = ReturnService._compute_refund(rr)
    currency = str(value.currency)
    already = Decimal(rr.refund.amount.amount) if rr.refund is not None else Decimal('0')
    owed = Decimal(value.amount) - Decimal(return_fee(rr.order).amount) - already
    if owed <= 0:
        return
    try:
        RefundService.process(order=rr.order, amount=Money(owed, currency), notes=note)
    except Exception as e:  # noqa: BLE001 — left for staff, said on the timeline
        logger.error('returns_portal: refund for unpaid exchange %s failed: %s', rr.rma_number, e)
        rr.order.log_event(
            'RETURN_REFUND_FAILED',
            message=f'Exchange #{exchange.order_number} was not paid; refunding {rr.rma_number} '
            f'failed: {e}',
        )
        return
    message = (
        f'Exchange #{exchange.order_number} was not paid in time, so return '
        f'{rr.rma_number} was refunded instead ({Money(owed, currency)}).'
    )
    rr.staff_note = f'{rr.staff_note}\n{message}'.strip()
    rr.save(update_fields=['staff_note', 'updated_at'])
    rr.order.log_event('RETURN_REFUNDED_INSTEAD', message=message)
    exchange.log_event('EXCHANGE_NOT_PAID', message=message)

"""Cancelling an order, and what happens to the money paid for it (v0.180.0).

Every door cancels through ``cancel_with_refund``: the customer's account, the
order page, the bulk action, Linda's ``orders.cancel`` and GraphQL
``cancelOrder``. Until v0.180.0 each cancelled in its own way: the account
refunded a paid order in full, and the other four cancelled from any status (a
delivered order too) and left the money where it was.

Two settings of the orders app decide the money, defaulting to what the store
did before:

- ``staff_cancel_refund``: 'keep' leaves a staff cancel's payment as it is
  (refunded from the order page's Issue refund); 'refund' pays back what is left
  of it.
- ``customer_cancel_paid``: 'refund' lets a customer cancel a paid order and
  pays it back in full; 'contact' lets them cancel only an unpaid one.

Safety rules that are not settings: an order cannot be cancelled once a parcel
of it has been recorded or it has shipped (it comes back as a return; what did
not ship is refunded from Issue refund), and a held card payment is released
by the payments app on ORDER_CANCELLED, never refunded.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction
from djmoney.money import Money

logger = logging.getLogger('morpheus.orders')

#: The statuses the order FSM's ``cancel`` leaves. ``fulfilled`` is cancellable
#: only while no parcel is recorded: with orders' ``fulfil_marks_shipped`` off,
#: an order whose parcels have all left stays ``fulfilled`` (``can_cancel``).
STAFF_CANCELLABLE = ('pending', 'confirmed', 'processing', 'fulfilled')
#: A customer cancels from their account only before the order is packed.
CUSTOMER_CANCELLABLE = ('pending', 'confirmed', 'processing')
#: Payment states in which money was taken and can be paid back.
MONEY_TAKEN = ('paid', 'partially_refunded')

STAFF_SETTING = ('keep', 'refund')
CUSTOMER_SETTING = ('refund', 'contact')


class CancelRefused(ValueError):
    """The order cannot be cancelled through this door; the message says why."""


@dataclass
class Cancellation:
    """The cancelled order, the refund made with it (if any), and one sentence
    on what happened to the money, for the door to show.

    ``refund_state``: 'none' (nothing to pay back), 'paid_back', 'waiting' (a
    refund is recorded and the gateway has not paid it yet) or 'failed' (the
    refund raised; the order stays cancelled and staff refund by hand).
    """

    order: Any
    refund: Any = None
    note: str = ''
    refund_state: str = 'none'


def _setting(key: str, allowed: tuple[str, ...]) -> str:
    from plugins.registry import app_registry  # noqa: PLC0415

    plugin = app_registry.get('orders')
    try:
        value = plugin.get_config_value(key, allowed[0]) if plugin else allowed[0]
    except Exception:  # noqa: BLE001 — a config problem keeps today's behaviour
        value = allowed[0]
    return value if value in allowed else allowed[0]


def staff_cancel_refunds() -> bool:
    """Whether a cancel from the dashboard, Linda or the API pays back what was paid."""
    return _setting('staff_cancel_refund', STAFF_SETTING) == 'refund'


def customer_may_cancel_paid() -> bool:
    """Whether a customer may cancel a paid order from their account."""
    return _setting('customer_cancel_paid', CUSTOMER_SETTING) == 'refund'


def refundable(order) -> Money:
    """What is left to pay back: the order total less every refund recorded on it,
    paid back or still waiting (a waiting one would otherwise be paid twice)."""
    recorded = sum((Decimal(r.amount.amount) for r in order.refunds.all()), Decimal('0'))
    left = max(Decimal('0'), Decimal(order.total.amount) - recorded)
    return Money(left, order.total.currency)


def can_cancel(order) -> bool:
    """Whether staff can cancel this order: it is open and no parcel of it has
    been recorded (cancelling one would re-credit gift cards and points in full
    and release stock that has left)."""
    return order.status in STAFF_CANCELLABLE and not order.fulfillments.exists()


def customer_can_cancel(order) -> bool:
    """Whether the customer can cancel this order from their account."""
    if order.status not in CUSTOMER_CANCELLABLE:
        return False
    return order.payment_status not in MONEY_TAKEN or customer_may_cancel_paid()


def _refund_plan(order, *, by_customer: bool) -> tuple[Money | None, str]:
    """(amount to pay back, or None; the sentence when nothing is paid back)."""
    if order.payment_status == 'authorized':
        return None, 'The held card payment is released.'
    if order.payment_status not in MONEY_TAKEN:
        return None, 'Nothing was paid, so there is nothing to pay back.'
    amount = refundable(order)
    if amount.amount <= 0:
        return None, 'Everything paid is already refunded or waiting to be.'
    if not by_customer and not staff_cancel_refunds():
        return None, 'The payment is left as it is: refund it from Issue refund.'
    return amount, ''


def preview(order) -> dict:
    """What a staff cancel of ``order`` would do, for the order page's confirmation."""
    if not can_cancel(order):
        return {'allowed': False, 'refund': None, 'note': ''}
    amount, note = _refund_plan(order, by_customer=False)
    return {'allowed': True, 'refund': amount, 'note': note}


def cancel_with_refund(
    order, *, reason: str = '', actor=None, by_customer: bool = False, withdrawal: bool = False
):
    """Cancel ``order`` and pay back what the settings say. Returns a ``Cancellation``.

    Raises ``CancelRefused`` when the order cannot be cancelled through this door.
    The cancel commits first, so a refund that fails leaves the order cancelled
    and the failure in ``note``; a refund the gateway has not completed stays on
    the order to settle, as from the refund form. ``order`` is read again under
    a lock, so a copy that went stale (the order shipped meanwhile) is refused.

    ``withdrawal``: the customer withdrew from the contract (orders/withdrawal.py,
    v0.181.0). The law gives the right whatever the settings say, so neither
    setting applies: an order none of which has left is cancelled and everything
    paid goes back, as a customer's own cancel does.
    """
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    with transaction.atomic():
        locked = Order.objects.select_for_update().filter(pk=order.pk).first()
        if locked is None:
            raise CancelRefused('This order no longer exists.')
        if withdrawal:
            if not can_cancel(locked):
                raise CancelRefused(_refusal(locked))
        elif by_customer:
            if locked.status not in CUSTOMER_CANCELLABLE:
                raise CancelRefused(
                    f'Order {locked.order_number} is already being sent, so it cannot be '
                    'cancelled here.'
                )
            if not customer_can_cancel(locked):
                raise CancelRefused(
                    f'Order {locked.order_number} is paid: contact the store to cancel it.'
                )
        elif not can_cancel(locked):
            raise CancelRefused(_refusal(locked))
        # A withdrawal pays back like a customer's own cancel: in full, through
        # the payment method.
        by_customer = by_customer or withdrawal
        amount, note = _refund_plan(locked, by_customer=by_customer)
        locked.cancel(reason=reason)
        locked.save()

    result = Cancellation(order=locked, note=note)
    if amount is None:
        return result
    return _pay_back(result, amount, reason=reason, actor=actor, by_customer=by_customer)


def _refusal(order) -> str:
    sent = {'shipped': 'has shipped', 'delivered': 'was delivered'}.get(order.status)
    if sent is None and order.status in STAFF_CANCELLABLE:
        sent = 'has a parcel on its way'
    if sent:
        return (
            f'Order {order.order_number} {sent}, so it cannot be cancelled: take it back '
            'as a return, or refund what did not ship from Issue refund.'
        )
    return f'Order {order.order_number} is already {order.status}.'


def _pay_back(result: Cancellation, amount: Money, *, reason, actor, by_customer):
    from plugins.installed.orders.refunds import RefundService, default_settle  # noqa: PLC0415

    order = result.order
    try:
        refund = RefundService.process(
            order=order,
            amount=amount,
            reason='customer_request' if by_customer else 'other',
            notes=f'Order cancelled: {reason}' if reason else 'Order cancelled',
            actor=actor,
            # A customer's click never records money as sent outside the store or
            # turns it into store credit: the account page promises the original
            # payment method, and staff settle what the gateway cannot.
            settle='' if by_customer else default_settle(order),
        )
    except Exception as e:  # noqa: BLE001 — the order stays cancelled; staff refund by hand
        logger.error(
            'orders: cancelled %s but the refund of %s failed: %s',
            order.order_number,
            amount,
            e,
        )
        result.note = f'The refund of {amount} failed ({e}): refund it from Issue refund.'
        result.refund_state = 'failed'
        return result
    result.refund = refund
    if refund.is_processed:
        result.refund_state = 'paid_back'
        result.note = f'{refund.amount} was paid back.'
    else:
        result.refund_state = 'waiting'
        result.note = (
            f'A refund of {refund.amount} is recorded; it has not been paid back yet. '
            'Settle it on the order page.'
        )
    return result

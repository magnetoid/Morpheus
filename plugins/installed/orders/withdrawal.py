"""Withdrawing from the contract for an order (EU Consumer Rights Directive,
Art. 11a, in force since 19 June 2026; v0.181.0).

returns_portal owns the page a customer uses ("Withdraw from contract here")
and its settings; this module owns the rule and the record, so Linda's tools
and the page withdraw the same way:

- Each line carries the right or says why not: a service booked for a set date
  has none, and digital content the customer asked to receive at once (the
  waiver ticked at checkout) loses it once the order is paid.
- The period is ``days`` (at least 14) from delivery for goods, and from the
  order for digital content. It has not started while goods are still to be
  sent. When no delivery is recorded, it counts from the last parcel plus
  ``TRANSIT_ALLOWANCE_DAYS``, so a store that never records deliveries does not
  close the period before the customer has the goods.
- An order none of which has left, every line of which carries the right, is
  cancelled and everything paid goes back (``cancel_with_refund``, withdrawal
  mode: the settings do not apply). Otherwise a return is requested for the
  lines that carry the right, and staff pay back once the goods are back.

The notice is stored before anything else happens, with the statement, the
lines and the time of submission, and ORDER_WITHDRAWAL_REQUESTED fires after
commit: returns_portal emails the acknowledgement.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from morpheus.core import MorpheusEvents, hook_registry

logger = logging.getLogger('morpheus.orders')

#: The shortest period the law allows; a merchant may set a longer one.
MIN_DAYS = 14
#: Days added to the last parcel's dispatch when no delivery is recorded.
TRANSIT_ALLOWANCE_DAYS = 30
#: How long a withdrawal still being acted on stops another from acting again.
IN_FLIGHT = timedelta(minutes=10)
#: Payment states in which a digital line counts as delivered.
_PAID = ('paid', 'partially_refunded')

REASON_SERVICE = 'A service booked for a set date: the right of withdrawal does not apply.'
REASON_WAIVED = (
    'Digital content you asked to receive at once: at checkout you accepted that the '
    'right of withdrawal ends when it is delivered.'
)


class WithdrawalRefused(ValueError):
    """The withdrawal cannot be recorded; the message says why."""


@dataclass
class LineRight:
    """Whether one order line carries the right of withdrawal today, and why not."""

    item: Any
    right: bool
    reason: str = ''
    #: The last day of the period, or None while it has not started.
    ends: date | None = None

    def as_record(self) -> dict:
        return {
            'order_item_id': str(self.item.pk),
            'product_name': self.item.product_name,
            'variant_name': self.item.variant_name,
            'quantity': self.item.quantity,
            'right': self.right,
            'reason': self.reason,
            'ends': self.ends.isoformat() if self.ends else '',
        }


def find_order(number: str, email: str):
    """The order with this number and email, or None. Both must match, so an order
    number alone reaches nothing (the page answers the same either way)."""
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    number = (number or '').strip()
    email = (email or '').strip()
    if not number or not email:
        return None
    return Order.objects.filter(order_number__iexact=number, email__iexact=email).first()


def _is_service(item) -> bool:
    return getattr(item.product, 'product_type', '') == 'service'


def _waived(order) -> bool:
    """The customer asked for the digital content at once at checkout, and it is
    delivered: the order is paid, or placed with a gateway paid later."""
    from plugins.installed.orders.tasks import OFFLINE_GATEWAYS  # noqa: PLC0415

    waiver = (order.metadata or {}).get('digital_withdrawal_waiver') or {}
    if not (isinstance(waiver, dict) and waiver.get('accepted')):
        return False
    return order.payment_status in _PAID or order.payment_gateway in OFFLINE_GATEWAYS


def _goods_start(order):
    """When the period for the goods starts, or None while some are still to leave."""
    from plugins.installed.orders.fulfilment import open_lines  # noqa: PLC0415

    parcels = list(order.fulfillments.all())
    sent = order.status in ('shipped', 'delivered') or (parcels and not open_lines(order))
    if not sent:
        return None
    delivered = [p.delivered_at for p in parcels if p.delivered_at]
    if parcels and len(delivered) == len(parcels):
        return max(delivered)
    event = order.events.filter(event_type='ORDER_DELIVERED').order_by('-created_at').first()
    if event is not None:
        return event.created_at
    dispatched = [p.shipped_at or p.created_at for p in parcels]
    if not dispatched:
        shipped = order.events.filter(event_type='ORDER_SHIPPED').order_by('-created_at').first()
        dispatched = [shipped.created_at if shipped else order.updated_at]
    return max(dispatched) + timedelta(days=TRANSIT_ALLOWANCE_DAYS)


def line_rights(order, *, days: int, today: date | None = None) -> list[LineRight]:
    """Each line of ``order`` with whether it carries the right today."""
    from plugins.installed.orders.services import line_ships  # noqa: PLC0415

    days = max(MIN_DAYS, int(days or MIN_DAYS))
    today = today or timezone.localdate()
    items = list(order.items.select_related('product', 'variant').order_by('product_name', 'pk'))
    goods_start = _goods_start(order) if any(line_ships(i) for i in items) else None
    waived = _waived(order)
    out = []
    for item in items:
        if _is_service(item):
            out.append(LineRight(item, False, REASON_SERVICE))
            continue
        if line_ships(item):
            start = goods_start
        elif waived:
            out.append(LineRight(item, False, REASON_WAIVED))
            continue
        else:
            start = order.placed_at
        if start is None:
            out.append(LineRight(item, True))
            continue
        ends = timezone.localtime(start).date() + timedelta(days=days)
        if today > ends:
            out.append(
                LineRight(item, False, f'The withdrawal period ended on {ends:%d %B %Y}.', ends)
            )
        else:
            out.append(LineRight(item, True, '', ends))
    return out


def statement_for(order, name: str) -> str:
    placed = timezone.localtime(order.placed_at)
    return (
        f'I, {name}, withdraw from my contract for order {order.order_number}, '
        f'placed on {placed:%d %B %Y}.'
    )


def withdraw(order, *, name: str, email: str, days: int, actor=None, source: str = 'customer'):
    """Record a withdrawal from ``order`` and act on it. Returns the ``WithdrawalNotice``.

    ``actor``: the signed-in customer, or the staff member who records a
    withdrawal sent another way (Linda's ``returns.process_withdrawal``).
    """
    from plugins.installed.orders.models import Order, WithdrawalNotice  # noqa: PLC0415

    name = (name or '').strip()[:200]
    email = (email or '').strip()
    if not name or not email:
        raise WithdrawalRefused('A withdrawal needs a name and an email for the acknowledgement.')
    user = actor if getattr(actor, 'is_authenticated', False) else None
    with transaction.atomic():
        locked = Order.objects.select_for_update().filter(pk=order.pk).first()
        if locked is None:
            raise WithdrawalRefused('This order no longer exists.')
        rights = line_rights(locked, days=days)
        earlier = locked.withdrawals.exists()
        # Another withdrawal recorded but not yet acted on (a double click, two
        # tabs): acting again would open a second return, or one on the order
        # the first is cancelling. A notice left unfinished by a crash stops
        # counting after IN_FLIGHT.
        in_flight = locked.withdrawals.filter(
            outcome='received', submitted_at__gte=timezone.now() - IN_FLIGHT
        ).exists()
        notice = WithdrawalNotice.objects.create(
            order=locked,
            name=name,
            email=email,
            statement=statement_for(locked, name),
            lines=[r.as_record() for r in rights],
            source=source if source in ('customer', 'staff') else 'customer',
            submitted_by=user,
        )

    if in_flight:
        outcome, note, refund, return_request = (
            'already',
            'Another withdrawal from this order was being processed.',
            None,
            None,
        )
    else:
        outcome, note, refund, return_request = _act(
            locked, rights, earlier=earlier, actor=user, statement=notice.statement
        )
    notice.outcome, notice.note = outcome, note
    notice.refund, notice.return_request = refund, return_request
    notice.save(update_fields=['outcome', 'note', 'refund', 'return_request'])
    locked.log_event('ORDER_WITHDRAWAL', message=f'{name} withdrew from the contract. {note}')
    transaction.on_commit(
        lambda: hook_registry.fire(
            MorpheusEvents.ORDER_WITHDRAWAL_REQUESTED, order=locked, withdrawal=notice
        )
    )
    return notice


def _plan(order, rights, *, earlier: bool) -> tuple[str, str, Any]:
    """(action, note, an open return) for a withdrawal of ``order`` now. The action is
    'already', 'nothing', 'cancel' or 'return'; nothing is changed."""
    from plugins.installed.orders.cancellation import can_cancel  # noqa: PLC0415

    if order.status in ('cancelled', 'refunded'):
        return ('already' if earlier else 'nothing'), f'The order is already {order.status}.', None
    eligible = [r for r in rights if r.right]
    if not eligible:
        return 'nothing', 'No line of this order carries the right of withdrawal now.', None
    open_return = _open_withdrawal_return(order)
    if open_return is not None:
        return 'already', f'Return {open_return.rma_number} is already open for it.', open_return
    if len(eligible) == len(rights) and can_cancel(order):
        return 'cancel', '', None
    return 'return', '', None


def _open_withdrawal_return(order):
    return (
        order.return_requests.filter(reason='withdrawal')
        .exclude(state__in=('rejected', 'cancelled'))
        .first()
    )


def preview(order, *, days: int) -> dict:
    """What a withdrawal from ``order`` would do now, for Linda before she asks:
    ``{'action', 'refund' (Money or None), 'rights'}``."""
    from plugins.installed.orders.cancellation import MONEY_TAKEN, refundable  # noqa: PLC0415

    rights = line_rights(order, days=days)
    action, note, _ = _plan(order, rights, earlier=order.withdrawals.exists())
    refund = None
    if action == 'cancel' and order.payment_status in MONEY_TAKEN:
        refund = refundable(order)
    return {'action': action, 'note': note, 'refund': refund, 'rights': rights}


def _act(order, rights, *, earlier: bool, actor, statement: str):
    """(outcome, note, refund, return request) for a withdrawal just recorded."""
    from plugins.installed.orders.cancellation import (  # noqa: PLC0415
        CancelRefused,
        cancel_with_refund,
    )
    from plugins.installed.orders.refunds import ReturnService  # noqa: PLC0415

    action, note, open_return = _plan(order, rights, earlier=earlier)
    if action in ('already', 'nothing'):
        return action, note, None, open_return
    if action == 'cancel':
        try:
            done = cancel_with_refund(
                order, reason='Withdrawal from the contract', actor=actor, withdrawal=True
            )
        except CancelRefused:
            pass  # a parcel left, or staff cancelled it, meanwhile: read again below
        else:
            return 'cancelled', f'The order is cancelled. {done.note}'.strip(), done.refund, None
    eligible = [r for r in rights if r.right]
    with transaction.atomic():
        # The plan was made from a copy read before the lock was let go: staff may
        # have cancelled the order since, or another withdrawal opened its return.
        current = type(order).objects.select_for_update().filter(pk=order.pk).first()
        if current is None:
            return 'nothing', 'This order no longer exists.', None, None
        if current.status in ('cancelled', 'refunded'):
            return 'already', f'The order is already {current.status}.', None, None
        open_return = _open_withdrawal_return(current)
        if open_return is not None:
            return (
                'already',
                f'Return {open_return.rma_number} is already open for it.',
                None,
                open_return,
            )
        rr = ReturnService.create_request(
            order=current,
            items=[
                {'order_item_id': str(r.item.pk), 'quantity': r.item.quantity} for r in eligible
            ],
            reason='withdrawal',
            customer_note=statement,
            requested_by=actor,
        )
    return (
        'return_requested',
        f'Return {rr.rma_number} is open: once the goods are back, the store pays back what '
        'they cost.',
        None,
        rr,
    )

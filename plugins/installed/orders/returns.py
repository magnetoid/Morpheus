"""Which lines of an order a customer may return (C4, v0.188.0).

A line comes back when all of these hold:

- the order is paid;
- the line ships (a download or a service never comes back);
- its units are in a parcel whose window is still open;
- no open or finished return already holds them.

Each parcel's window starts at its delivery, else at its dispatch plus the transit
allowance the withdrawal rule uses, so what the store tells search engines about its
window stays true. A unit belongs to the earliest parcel that holds it. An exchange
order is never returned online: a fault with a replacement goes to the store.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.utils import timezone

#: The order states that mean the money was taken.
PAID = ('paid', 'partially_refunded')
#: Return states that no longer hold their units.
RELEASED = ('rejected', 'cancelled')


class ReturnRefused(ValueError):
    """The request names a line or units that cannot be returned."""


@dataclass(frozen=True)
class ReturnableLine:
    item: object
    units: int
    reason: str = ''
    window_ends: date | None = None


def parcel_start(fulfillment) -> datetime:
    """When a parcel's return window starts: its delivery, else its dispatch plus
    the transit allowance."""
    from plugins.installed.orders.withdrawal import TRANSIT_ALLOWANCE_DAYS  # noqa: PLC0415

    if fulfillment.delivered_at:
        return fulfillment.delivered_at
    sent = fulfillment.shipped_at or fulfillment.created_at
    return sent + timedelta(days=TRANSIT_ALLOWANCE_DAYS)


def held_units(order) -> dict[str, int]:
    """Units of each line that an open or finished return already holds."""
    held: dict[str, int] = {}
    for rr in order.return_requests.exclude(state__in=RELEASED):
        for entry in rr.items or []:
            key = str(entry.get('order_item_id', ''))
            held[key] = held.get(key, 0) + int(entry.get('quantity', 0) or 0)
    return held


def _sent_batches(order) -> dict[str, list[tuple[int, date]]]:
    """For each line, (units, window start date) per parcel, earliest first."""
    batches: dict[str, list[tuple[int, date]]] = {}
    for parcel in order.fulfillments.prefetch_related('items'):
        start = timezone.localdate(parcel_start(parcel))
        for fi in parcel.items.all():
            batches.setdefault(str(fi.order_item_id), []).append((fi.quantity, start))
    for rows in batches.values():
        rows.sort(key=lambda row: row[1])
    return batches


def returnable_lines(order, *, window_days: int, today: date | None = None) -> list[ReturnableLine]:
    """Every line of ``order`` with the units it may still return, or why not."""
    from plugins.installed.orders.services import line_ships  # noqa: PLC0415

    today = today or timezone.localdate()
    items = list(order.items.select_related('product', 'variant'))
    if (order.metadata or {}).get('exchange_of'):
        return [ReturnableLine(item, 0, 'exchange_order') for item in items]
    if order.payment_status not in PAID:
        return [ReturnableLine(item, 0, 'not_paid') for item in items]
    batches = _sent_batches(order)
    held = held_units(order)
    result = []
    for item in items:
        if not line_ships(item):
            result.append(ReturnableLine(item, 0, 'does_not_ship'))
            continue
        rows = batches.get(str(item.pk), [])
        if not rows:
            result.append(ReturnableLine(item, 0, 'not_sent'))
            continue
        if window_days <= 0:
            result.append(ReturnableLine(item, 0, 'window_closed'))
            continue
        open_units, ends = 0, None
        for units, start in rows:
            closes = start + timedelta(days=window_days)
            if today <= closes:
                open_units += units
                ends = closes if ends is None else min(ends, closes)
        # Held units come off the closed parcels first: what is free is what is
        # open, capped by what was sent and is not yet held.
        sent = sum(units for units, _start in rows)
        free = max(0, min(open_units, sent - held.get(str(item.pk), 0)))
        if open_units == 0:
            result.append(ReturnableLine(item, 0, 'window_closed'))
        elif free == 0:
            result.append(ReturnableLine(item, 0, 'already_returned', ends))
        else:
            result.append(ReturnableLine(item, free, '', ends))
    return result


def check_request(order, items: list[dict], *, window_days: int) -> None:
    """Refuse a request naming a line or more units than may come back."""
    allowed = {
        str(line.item.pk): line.units for line in returnable_lines(order, window_days=window_days)
    }
    asked: dict[str, int] = {}
    for entry in items:
        key = str(entry.get('order_item_id', ''))
        asked[key] = asked.get(key, 0) + int(entry.get('quantity', 0) or 0)
    if not asked or any(qty <= 0 or qty > allowed.get(key, 0) for key, qty in asked.items()):
        raise ReturnRefused('Those items can no longer be returned.')

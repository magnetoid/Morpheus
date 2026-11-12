"""Shipping an order in one or more parcels.

Every way a parcel leaves the store goes through ``create_fulfillment``: the
dashboard's fulfil form, Linda's ``orders.fulfill_lines`` and the supplier apps
(``plugins/dropshipping/orders.py``). It records which units went out, moves the
order along its state machine and fires ``FULFILLMENT_CREATED`` once the parcel
is committed.

Only lines that need a parcel count (``orders.services.line_ships``): a
download reaches the buyer by itself (digital_products), so an order whose
parcels hold every unit that ships is complete.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('morpheus.orders')

# A parcel can leave an order in any of these states; pending and confirmed are
# walked forward first, as a supplier's shipment always did. 'fulfilled' is here
# because GraphQL's markOrderFulfilled sets it without recording any parcel.
FULFILLABLE_STATUSES = ('pending', 'confirmed', 'processing', 'partially_fulfilled', 'fulfilled')

FULFILLMENT_STATUSES = ('pending', 'in_transit', 'delivered', 'failed', 'returned')


class FulfilmentError(ValueError):
    """A parcel that cannot be recorded; the message is fit for the merchant."""


def open_lines(order) -> list[tuple]:
    """``[(item, remaining)]`` for every line that ships and still has units to send."""
    from plugins.installed.orders.services import line_ships  # noqa: PLC0415

    out = []
    for item in order.items.select_related('product', 'variant').order_by('product_name', 'pk'):
        remaining = item.quantity - item.fulfilled_quantity
        if remaining > 0 and line_ships(item):
            out.append((item, remaining))
    return out


def is_complete(order) -> bool:
    """Every unit that ships is in a parcel (an order with nothing to ship is not)."""
    from plugins.installed.orders.services import line_ships  # noqa: PLC0415

    shipping = [i for i in order.items.select_related('product', 'variant') if line_ships(i)]
    return bool(shipping) and all(i.fulfilled_quantity >= i.quantity for i in shipping)


def _quantities(order, lines: dict | None) -> list[tuple]:
    """Validate ``lines`` ({order item id: units}) against what is still open."""
    available = open_lines(order)
    if not available:
        raise FulfilmentError('Nothing in this order is left to ship.')
    if lines is None:
        return available
    by_id = {str(item.pk): (item, remaining) for item, remaining in available}
    chosen = []
    for raw_id, raw_qty in lines.items():
        try:
            qty = int(raw_qty)
        except (TypeError, ValueError):
            raise FulfilmentError('Each quantity must be a whole number.') from None
        if qty < 0:
            raise FulfilmentError('A quantity cannot be negative.')
        if qty == 0:
            continue
        if str(raw_id) not in by_id:
            raise FulfilmentError('A line in the parcel is not open on this order.')
        item, remaining = by_id[str(raw_id)]
        if qty > remaining:
            raise FulfilmentError(
                f'Only {remaining} of "{item.product_name}" are left to ship, not {qty}.'
            )
        chosen.append((item, qty))
    if not chosen:
        raise FulfilmentError('Choose at least one unit to ship.')
    return chosen


def create_fulfillment(  # noqa: PLR0913
    order,
    lines: dict | None = None,
    *,
    tracking_number: str = '',
    tracking_url: str = '',
    carrier: str = '',
    notes: str = '',
    status: str = 'in_transit',
    mark_shipped: bool = True,
):
    """Record a parcel and return the ``Fulfillment``.

    ``lines`` maps order item ids to the units in this parcel; ``None`` sends
    every unit still open. A parcel that leaves units behind moves the order to
    *partially fulfilled*; the one that completes it ships the order
    (``mark_shipped``) or marks it fulfilled, which fires ``ORDER_FULFILLED``
    through orders' own signal. Raises ``FulfilmentError`` with a message for
    the merchant.
    """
    from django_fsm import can_proceed  # noqa: PLC0415

    from morpheus.core import MorpheusEvents, hook_registry  # noqa: PLC0415
    from plugins.installed.orders.models import Fulfillment, FulfillmentItem, Order  # noqa: PLC0415

    if status not in FULFILLMENT_STATUSES:
        raise FulfilmentError('Unknown shipment status.')
    tracking_number = (tracking_number or '').strip()[:200]
    tracking_url = (tracking_url or '').strip()
    if len(tracking_url) > 200:
        # The column holds 200 characters, and a cut URL is a broken link.
        tracking_url = ''
    with transaction.atomic():
        # Lock the row and work on the caller's own instance, so a caller that
        # reads it afterwards sees the parcel's effect; one that is out of date
        # (another parcel or a cancel since it was loaded) is refused.
        current = (
            Order.objects.select_for_update()
            .filter(pk=order.pk)
            .values_list('status', flat=True)
            .first()
        )
        if current != order.status:
            raise FulfilmentError('This order changed meanwhile; reload it and try again.')
        if order.status not in FULFILLABLE_STATUSES:
            raise FulfilmentError(
                f'An order that is {order.get_status_display().lower()} cannot ship a parcel.'
            )
        chosen = _quantities(order, lines)
        fulfillment = Fulfillment.objects.create(
            order=order,
            status=status,
            tracking_number=tracking_number,
            tracking_url=tracking_url,
            carrier=(carrier or '').strip()[:100],
            notes=notes or '',
            shipped_at=timezone.now() if status != 'pending' else None,
        )
        for item, qty in chosen:
            FulfillmentItem.objects.create(fulfillment=fulfillment, order_item=item, quantity=qty)
            item.fulfilled_quantity += qty
            item.save(update_fields=['fulfilled_quantity'])

        complete = is_complete(order)
        prior = order.status
        if tracking_number or order.fulfillments.exclude(pk=fulfillment.pk).exists():
            # Before the transition: the "on its way" email it sends quotes this
            # parcel, never an earlier box's number when this one has none.
            order.tracking_number = tracking_number
        if order.status == 'pending':
            order.confirm()
        if order.status == 'confirmed':
            order.process()
        if complete and mark_shipped and can_proceed(order.ship):
            order.ship(tracking_number=tracking_number)
        elif complete and can_proceed(order.fulfill):
            order.fulfill()
        elif not complete and can_proceed(order.fulfill_partially):
            order.fulfill_partially(fulfillment)
        # ORDER_FULFILLED (the "on its way" email) went out in this call; it does
        # not when the order was already fulfilled without a parcel, nor when it
        # could not move on, so the parcel's own email must tell the buyer.
        announced = complete and prior not in ('fulfilled', order.status)
        order.save()

        def _announce():
            try:
                hook_registry.fire(
                    MorpheusEvents.FULFILLMENT_CREATED,
                    order=order,
                    fulfillment=fulfillment,
                    complete=complete,
                    announced=announced,
                )
            except Exception:  # noqa: BLE001 — a side effect never undoes a shipment
                logger.warning('order %s: fulfillment hook failed', order.pk, exc_info=True)

        transaction.on_commit(_announce)
    return fulfillment

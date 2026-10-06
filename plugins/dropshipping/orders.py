"""Which orders go to a supplier, and how one comes back shipped."""

from __future__ import annotations

from urllib.parse import quote

from django.utils import timezone

DEFAULT_TRACKING_URL = 'https://t.17track.net/en#nums={tracking}'

# Paid orders that have not gone out yet. 'processing' is included because a
# merchant may have moved an order there by hand before handing it over.
EXPORTABLE_STATUSES = ('confirmed', 'processing')


def shippable(item) -> bool:
    """Does this order line need a parcel? Digital and virtual lines never go to a supplier."""
    variant = item.variant
    if variant is not None:
        return bool(variant.requires_shipping)
    product = item.product
    if product is not None:
        return product.product_type != 'digital'
    return True


def eligible_orders(exclude_relation: str) -> list:
    """Paid, confirmed/processing orders with a shippable line and no supplier
    record yet — ``exclude_relation`` is the app's OneToOne reverse name on Order."""
    from plugins.installed.orders.models import Order

    qs = (
        Order.objects.filter(
            payment_status='paid',
            status__in=EXPORTABLE_STATUSES,
            **{f'{exclude_relation}__isnull': True},
        )
        .order_by('placed_at')
        .prefetch_related('items__variant', 'items__product')
    )
    return [order for order in qs if any(shippable(i) for i in order.items.all())]


def tracking_url(template: str, tracking: str) -> str:
    template = template or DEFAULT_TRACKING_URL
    if '{tracking}' in template:
        return template.replace('{tracking}', quote(tracking, safe=''))
    return template


def ship_with_tracking(order, tracking: str, *, carrier: str = '', url: str = ''):
    """Ship ``order`` with ``tracking`` the platform way and return the Fulfillment.

    Creates the ``orders.Fulfillment`` (+ items for every unfulfilled quantity)
    and walks the state machine to *shipped* from wherever the order is, so
    ``ORDER_FULFILLED`` fires once through orders' own signal. Callers wrap this
    in a transaction together with their own bookkeeping.
    """
    from plugins.installed.orders.models import Fulfillment, FulfillmentItem

    fulfillment = Fulfillment.objects.create(
        order=order,
        status='in_transit',
        tracking_number=tracking,
        tracking_url=url,
        carrier=carrier,
        shipped_at=timezone.now(),
    )
    for item in order.items.all():
        remaining = item.quantity - item.fulfilled_quantity
        if remaining > 0:
            FulfillmentItem.objects.create(
                fulfillment=fulfillment, order_item=item, quantity=remaining
            )
            item.fulfilled_quantity = item.quantity
            item.save(update_fields=['fulfilled_quantity'])
    if order.status == 'pending':
        order.confirm()
    if order.status == 'confirmed':
        order.process()
    if order.status in ('processing', 'fulfilled', 'partially_fulfilled'):
        order.ship(tracking_number=tracking)
    else:
        order.tracking_number = tracking
    order.save()
    return fulfillment

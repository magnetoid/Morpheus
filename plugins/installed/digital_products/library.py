"""A customer's library: the digital lines of their orders, listed like orders.

One rule, read by the library page, the order pages, the account tile, the file view
and the emailed links: a digital line is delivered the moment its order is paid, the
moment an order paid later (cash on delivery, bank transfer) is placed, or once the
store has fulfilled or shipped it. A card order waits for the card, which takes
seconds; an order paid later is the store already trusting the buyer, as it does when
it sends a parcel before the money. A digital line never waits for a fulfilment or a
tracking number. A cancelled or refunded order delivers nothing.

A delivered line still needs its file: an audiobook whose narration is not made yet
shows as being prepared, and becomes playable the moment its file exists. The file
comes from ``delivery_file``: the variant's own, else the product's, else whatever
the app that owns the edition answers on ``DIGITAL_DELIVERY_FILE``.

Until v0.148.0 the account listed only download links, which expire after a week and
were minted only on payment, so every order paid on delivery showed nothing, and the
owner delivered a PDF by creating a shipment with a tracking number.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger('morpheus.digital_products')

DIGITAL_VARIANT_TYPES = ('digital', 'audiobook')
DELIVERED_STATUSES = ('fulfilled', 'shipped', 'delivered')
CLOSED_STATUSES = ('cancelled', 'refunded')

READY = 'ready'
WAITING = 'waiting'
PREPARING = 'preparing'

_STATE_LABELS = {
    READY: 'Ready',
    WAITING: 'Waiting for payment',
    PREPARING: 'Being prepared',
}


@dataclass
class LibraryItem:
    id: str
    name: str
    edition: str
    kind: str  # 'audio' or 'file'
    image_url: str
    order_number: str
    ordered_at: datetime | None
    state: str
    state_label: str
    product_url: str
    file_url: str
    listen_url: str


def digital_lines(user):
    """The customer's digital order lines, newest order first, closed orders left out."""
    from django.db.models import Q

    from plugins.installed.orders.models import OrderItem

    return (
        OrderItem.objects.filter(order__customer=user)
        .filter(
            Q(variant__variant_type__in=DIGITAL_VARIANT_TYPES) | Q(product__product_type='digital')
        )
        .exclude(order__status__in=CLOSED_STATUSES)
        .exclude(order__payment_status='refunded')
        .select_related('order', 'product', 'variant')
        .order_by('-order__placed_at', 'id')
    )


def is_closed(order) -> bool:
    """A cancelled or refunded order, which delivers nothing."""
    return order.status in CLOSED_STATUSES or order.payment_status == 'refunded'


def is_delivered(order) -> bool:
    from plugins.installed.orders.tasks import OFFLINE_GATEWAYS

    if is_closed(order):
        return False
    return (
        order.payment_status == 'paid'
        or order.status in DELIVERED_STATUSES
        or order.payment_gateway in OFFLINE_GATEWAYS
    )


def is_digital(item) -> bool:
    variant = getattr(item, 'variant', None)
    if variant is not None and variant.variant_type in DIGITAL_VARIANT_TYPES:
        return True
    product = getattr(item, 'product', None)
    return product is not None and product.product_type == 'digital'


def delivery_file(item):
    """The file this order line delivers, or None."""
    variant = getattr(item, 'variant', None)
    product = getattr(item, 'product', None)
    digital = (getattr(variant, 'digital_file', None) if variant is not None else None) or None
    # The product's file stands in for an edition without one, except an audiobook:
    # the book's PDF is not its narration, whether or not the audiobooks app is on.
    edition = getattr(variant, 'variant_type', '') if variant is not None else ''
    if not digital and product is not None and edition != 'audiobook':
        digital = getattr(product, 'digital_file', None) or None
    try:
        from morpheus.core import MorpheusEvents, hook_registry

        digital = hook_registry.filter(
            MorpheusEvents.DIGITAL_DELIVERY_FILE,
            value=digital,
            order_item=item,
            variant=variant,
            product=product,
        )
    except Exception:  # noqa: BLE001 — a broken answer must not hide the variant's own file
        logger.warning('digital delivery file lookup failed for %s', item.pk, exc_info=True)
    return digital or None


def line_state(item) -> str:
    if not is_delivered(item.order):
        return WAITING
    return READY if delivery_file(item) else PREPARING


def _item(line) -> LibraryItem:
    variant = line.variant
    product = line.product
    state = line_state(line)
    kind = 'audio' if variant is not None and variant.variant_type == 'audiobook' else 'file'
    base = f'/account/library/{line.pk}/file/'
    return LibraryItem(
        id=str(line.pk),
        name=line.product_name or (product.name if product is not None else ''),
        edition=line.variant_name or (variant.name if variant is not None else ''),
        kind=kind,
        image_url=line.image_url,
        order_number=line.order.order_number,
        ordered_at=line.order.placed_at,
        state=state,
        state_label=_STATE_LABELS[state],
        product_url=f'/products/{product.slug}/' if product is not None and product.slug else '',
        file_url=base if state == READY else '',
        listen_url=f'{base}?play=1' if state == READY and kind == 'audio' else '',
    )


def line_delivery(item) -> dict | None:
    """How one order line reaches its buyer, for the order pages; None for goods.

    A signed-in buyer's links go through their library; a guest's through the
    emailed download link, the only door a guest has.
    """
    if not is_digital(item):
        return None
    # A closed order delivers nothing and its page already says why; "waiting for
    # payment" on a cancelled order was wrong (v0.148.1).
    if is_closed(item.order):
        return None
    entry = _item(item)
    if entry.state == READY and item.order.customer_id is None:
        from plugins.installed.digital_products.models import DownloadToken

        token = DownloadToken.objects.filter(order_item=item).order_by('-created_at').first()
        url = f'/digital/download/{token.token}/' if token is not None and token.is_active else ''
        entry.file_url = url
        entry.listen_url = ''
        if not url:
            entry.state, entry.state_label = PREPARING, 'Link sent by email'
    return {
        'state': entry.state,
        'state_label': entry.state_label,
        'kind': entry.kind,
        'file_url': entry.file_url,
        'listen_url': entry.listen_url,
    }


def library(user, limit: int = 200) -> list[LibraryItem]:
    return [_item(line) for line in digital_lines(user)[:limit]]


def count(user) -> int:
    return digital_lines(user).count()


def owned_line(user, item_id):
    """The customer's delivered order line with this id, or None."""
    line = digital_lines(user).filter(pk=item_id).first()
    if line is None or not is_delivered(line.order):
        return None
    return line

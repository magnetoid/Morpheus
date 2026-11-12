"""The order page's "Shipping labels" panel (``ORDER_DETAIL_PANELS``)."""

from __future__ import annotations

from typing import Any


def order_panel(value, order=None, request=None, **_: Any):
    """Each parcel's label, or a button to buy one, while a carrier is set up.

    Shown only for an order with something that ships; a store with no carrier
    sees no panel unless the order already has labels.
    """
    if order is None or not isinstance(value, list):
        return value
    from django.template.loader import render_to_string  # noqa: PLC0415

    from plugins.installed.orders.fulfilment import (  # noqa: PLC0415
        FULFILLABLE_STATUSES,
        open_lines,
    )
    from plugins.installed.orders.services import line_ships  # noqa: PLC0415
    from plugins.installed.shipping.labels import NAMES, configured_providers  # noqa: PLC0415
    from plugins.installed.shipping.models import ShippingLabel  # noqa: PLC0415

    providers = configured_providers()
    labels = list(ShippingLabel.objects.filter(order=order))
    if not providers and not labels:
        return value
    if not any(line_ships(i) for i in order.items.select_related('product', 'variant')):
        return value
    by_parcel = {label.fulfillment_id: label for label in labels if label.fulfillment_id}
    parcels = [
        {'parcel': parcel, 'label': by_parcel.get(parcel.pk)}
        for parcel in order.fulfillments.order_by('created_at')
    ]
    html = render_to_string(
        'shipping/dashboard/order_labels_panel.html',
        {
            'order': order,
            'parcels': parcels,
            'loose_labels': [label for label in labels if not label.fulfillment_id],
            'providers': [(p, NAMES[p]) for p in providers],
            'can_ship_rest': bool(providers)
            and order.status in FULFILLABLE_STATUSES
            and bool(open_lines(order)),
        },
        request=request,
    )
    value.append({'label': 'Shipping labels', 'html': html, 'priority': 30})
    return value

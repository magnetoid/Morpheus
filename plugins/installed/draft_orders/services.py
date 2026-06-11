"""Draft-order services — recalc + convert-to-order."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.db import transaction

logger = logging.getLogger('morpheus.draft_orders')


def recalc(draft) -> None:
    """Recompute subtotal/total from the draft's lines."""
    from djmoney.money import Money

    currency = str(getattr(draft.subtotal, 'currency', 'USD'))
    subtotal = Decimal('0')
    for line in draft.lines.all():
        try:
            subtotal += Decimal(str(line.unit_price.amount)) * Decimal(line.quantity)
        except Exception:  # noqa: BLE001, S112
            continue
    draft.subtotal = Money(subtotal, currency)
    draft.total = Money(
        subtotal
        + Decimal(str(getattr(draft.tax_total, 'amount', 0)))
        + Decimal(str(getattr(draft.shipping_total, 'amount', 0)))
        - Decimal(str(getattr(draft.discount_total, 'amount', 0))),
        currency,
    )
    draft.save(update_fields=['subtotal', 'total', 'updated_at'])


@transaction.atomic
def convert_to_order(draft) -> Any:
    """Spawn a real `orders.Order` from this draft. Returns the new Order."""
    from plugins.installed.orders.models import Order, OrderItem

    if draft.status == 'converted' and draft.converted_order_id:
        return Order.objects.get(pk=draft.converted_order_id)

    order = Order.objects.create(
        customer=draft.customer,
        email=draft.customer_email or (draft.customer.email if draft.customer else ''),
        channel=draft.channel,
        subtotal=draft.subtotal,
        tax_total=draft.tax_total,
        shipping_total=draft.shipping_total,
        discount_total=draft.discount_total,
        total=draft.total,
        shipping_address=draft.shipping_address,
        billing_address=draft.billing_address,
        customer_notes=draft.note,
        source='draft',
    )
    for line in draft.lines.all():
        OrderItem.objects.create(
            order=order,
            variant=line.variant,
            product=getattr(line.variant, 'product', None) if line.variant else None,
            product_name=line.product_name,
            sku=line.sku,
            unit_price=line.unit_price,
            quantity=line.quantity,
            total_price=line.unit_price * line.quantity,
        )
    draft.status = 'converted'
    draft.converted_order_id = str(order.id)
    draft.save(update_fields=['status', 'converted_order_id', 'updated_at'])
    return order

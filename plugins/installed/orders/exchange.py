"""Exchanging returned goods for another edition (C4, v0.188.0).

The exchange is an order of its own, linked to the return
(``metadata['exchange_of']`` = the RMA number). It goes through stock, parcels and
the shipping emails like any order. Each new line is priced at what the customer
paid for the unit sent back, and that whole amount is the order's discount, so it
costs nothing but the exchange fee the merchant set, if any (in ``shipping_total``,
"Exchange fee").

It never fires ORDER_PLACED or ORDER_PAID when free: GA4, the ad conversion APIs,
loyalty points, affiliates and the receipt would all count a purchase nobody made.
A charged one stays unpaid; returns_portal sends it the payment link, and paying it
fires ORDER_PAID like any order, since that money is real.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry

logger = logging.getLogger('morpheus.orders.exchange')

FEE_LABEL = 'Exchange fee'


@dataclass(frozen=True)
class ExchangeLine:
    order_item_id: str
    variant_id: str
    quantity: int = 1


def paid_unit_price(item) -> Money:
    """What the customer paid for one unit of ``item``: its list price less its
    share of the order's discount (the proration ``_compute_refund`` uses)."""
    order = item.order
    price = Decimal(item.unit_price.amount)
    subtotal = Decimal(order.subtotal.amount)
    discount = Decimal(order.discount_total.amount)
    if subtotal > 0 and discount > 0:
        price -= discount * (price / subtotal)
    return Money(max(price, Decimal('0')).quantize(Decimal('0.01')), str(item.unit_price.currency))


def units_available(variant_ids: list) -> dict[str, int]:
    """Units the stock reservation could take per variant (inventory answers;
    a variant with no stock row is untracked and left out)."""
    try:
        return (
            hook_registry.filter(
                MorpheusEvents.VARIANT_STOCK_SUMMARY, value={}, variant_ids=variant_ids
            )
            or {}
        )
    except Exception:  # noqa: BLE001 — no answer reads as untracked
        logger.warning('orders: stock summary for an exchange failed', exc_info=True)
        return {}


def _makeable(rr, lines: list[ExchangeLine]) -> tuple[list[tuple], list[ExchangeLine]]:
    """Split ``lines`` into (item, variant, quantity) that can be made and the rest.

    A line is made when its returned item is in the return, the new edition is
    another active edition of the same product that is for sale, costs no more than
    was paid, and is in stock."""
    from plugins.installed.catalog.models import ProductVariant  # noqa: PLC0415

    returned = {str(e.get('order_item_id')): int(e.get('quantity', 0) or 0) for e in rr.items or []}
    items = {str(i.pk): i for i in rr.order.items.select_related('product', 'variant')}
    variants = {
        str(v.pk): v
        for v in ProductVariant.objects.select_related('product').filter(
            pk__in=[line.variant_id for line in lines]
        )
    }
    stock = units_available(list(variants))
    made, unmade = [], []
    for line in lines:
        item = items.get(str(line.order_item_id))
        variant = variants.get(str(line.variant_id))
        qty = min(int(line.quantity or 0), returned.get(str(line.order_item_id), 0))
        ok = (
            item is not None
            and variant is not None
            and qty > 0
            and variant.product_id == item.product_id
            and variant.pk != item.variant_id
            and getattr(variant, 'is_active', True)
            and variant.is_for_sale
            and variant.effective_price is not None
            and variant.effective_price.amount <= paid_unit_price(item).amount
            and stock.get(str(variant.pk), qty) >= qty
        )
        if ok:
            made.append((item, variant, qty))
        else:
            unmade.append(line)
    return made, unmade


def difference(made: list[tuple]) -> Money | None:
    """What the customer gets back for the cheaper editions, or None with no lines."""
    if not made:
        return None
    currency = str(made[0][0].unit_price.currency)
    total = Decimal('0')
    for item, variant, qty in made:
        total += (
            max(
                Decimal('0'),
                Decimal(paid_unit_price(item).amount) - Decimal(variant.effective_price.amount),
            )
            * qty
        )
    return Money(total, currency)


def create_exchange_order(rr, made: list[tuple], *, fee: Money):
    """Build the exchange order for ``made`` lines, charging ``fee`` (0 = free).

    Runs inside the caller's transaction; raises when the stock reservation refuses."""
    from plugins.installed.orders.models import Order, OrderItem  # noqa: PLC0415

    source = rr.order
    currency = str(source.total.currency)
    lines = [(item, variant, qty, paid_unit_price(item)) for item, variant, qty in made]
    subtotal = sum((Decimal(price.amount) * qty for _i, _v, qty, price in lines), Decimal('0'))
    fee_amount = max(Decimal('0'), Decimal(fee.amount)) if fee is not None else Decimal('0')
    order = Order.objects.create(
        customer=source.customer,
        email=source.email,
        channel=source.channel,
        shipping_address=source.shipping_address,
        billing_address=source.billing_address,
        subtotal=Money(subtotal, currency),
        discount_total=Money(subtotal, currency),
        shipping_total=Money(fee_amount, currency),
        total=Money(fee_amount, currency),
        shipping_method=FEE_LABEL if fee_amount > 0 else '',
        source='exchange',
        metadata={'exchange_of': rr.rma_number, 'return_id': str(rr.pk)},
    )
    for item, variant, qty, price in lines:
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            product_name=item.product_name,
            variant_name=variant.name,
            sku=variant.sku or item.sku,
            image_url=item.image_url,
            quantity=qty,
            unit_price=price,
            total_price=Money(Decimal(price.amount) * qty, currency),
        )
    hook_registry.filter(
        MorpheusEvents.ORDER_RESERVE_STOCK, value=0, order=order, raise_errors=True
    )
    if fee_amount <= 0:
        # Settled here rather than by settle_free_order, which fires ORDER_PAID.
        order.payment_status = 'paid'
        order.confirm()
        order.save(update_fields=['payment_status', 'status'])
    order.log_event('EXCHANGE_CREATED', message=f'Exchange for return {rr.rma_number}')
    source.log_event(
        'EXCHANGED_FOR', message=f'Return {rr.rma_number} → order #{order.order_number}'
    )
    return order


def make_exchange(rr, lines: list[ExchangeLine], *, fee: Money):
    """(exchange order or None, lines not made, the difference to refund).

    The fee first comes off the difference; what is left of it goes on the order."""
    made, unmade = _makeable(rr, lines)
    if not made:
        return None, list(lines), None
    back = difference(made)
    fee = fee if fee is not None else Money(0, str(back.currency))
    taken = min(Decimal(fee.amount), Decimal(back.amount))
    back_after = Money(Decimal(back.amount) - taken, str(back.currency))
    owed = Money(max(Decimal('0'), Decimal(fee.amount) - taken), str(back.currency))
    try:
        with transaction.atomic():
            order = create_exchange_order(rr, made, fee=owed)
    except Exception:  # noqa: BLE001 — the stock refused: the whole exchange is refunded
        logger.warning('orders: exchange for %s refused by the stock', rr.rma_number, exc_info=True)
        return None, list(lines), None
    return order, unmade, back_after

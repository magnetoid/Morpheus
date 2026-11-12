"""What the store sold: the one rule every sales report reads.

An order counts once it is placed and not cancelled: paid, its card held, or
placed with a method paid later (cash on delivery, bank transfer). An order
left unpaid at the payment step, a cancelled one and one whose card hold was
given back do not count. A paid order counts whatever its status says: Stripe's
webhook left paid orders 'pending' until it was fixed, so older ones still are. Its sales are its total minus the refunds processed
on it, whenever they were made, so a period's figure says what its orders
brought in after their returns.

Until v0.157.0 each report had its own rule: the home tiles, the Sales page,
Linda's summaries and the cohorts counted every order, cancelled and unpaid
ones too, or statuses no order ever has ('paid', 'completed').
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from django.db.models import Count, Max, Q, Sum

from plugins.installed.orders.services import PAID_STATUSES

#: The order statuses that count as a sale. 'refunded' counts, at nothing once
#: its refunds are netted, so the order is still one the store took.
SALE_STATUSES = (*PAID_STATUSES, 'refunded')
#: Payment states that say the money was taken or is held.
_MONEY_TAKEN = ('paid', 'authorized', 'partially_refunded', 'refunded')

_ZERO = Decimal('0.00')


@dataclass
class Sales:
    """A period's counted orders and what they brought in, in one currency."""

    orders: int = 0
    gross: Decimal = _ZERO
    refunds: Decimal = _ZERO
    net: Decimal = _ZERO
    currency: str = ''
    #: Net sales in any other currency, which the figures above leave out.
    others: dict = field(default_factory=dict)


def counted(qs=None):
    """The orders in ``qs`` (default: all) that count as sales."""
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    qs = Order.objects.all() if qs is None else qs
    return qs.filter(
        Q(status__in=SALE_STATUSES) | (Q(payment_status__in=_MONEY_TAKEN) & ~Q(status='cancelled'))
    ).exclude(payment_status='released')


def _refunds_by(orders, *keys):
    from plugins.installed.orders.models import Refund  # noqa: PLC0415

    return (
        Refund.objects.filter(order__in=orders.values('pk'), is_processed=True)
        .values(*keys)
        .annotate(s=Sum('amount'))
    )


def net_sales(qs=None) -> Sales:
    """Counted orders in ``qs``, their totals and refunds, per currency.

    The figures are in the currency most of the orders carry; amounts in any
    other currency are in ``others`` and never added to them.
    """
    orders = counted(qs)
    per = {
        row['total_currency']: (row['n'], Decimal(str(row['t'] or 0)))
        for row in orders.values('total_currency').annotate(n=Count('id'), t=Sum('total'))
    }
    if not per:
        return Sales()
    refunds: dict = defaultdict(Decimal)
    for row in _refunds_by(orders, 'order__total_currency'):
        refunds[row['order__total_currency']] += Decimal(str(row['s'] or 0))
    currency = Counter({code: n for code, (n, _) in per.items()}).most_common(1)[0][0]
    n, gross = per[currency]
    refunded = refunds[currency]
    return Sales(
        orders=n,
        gross=gross.quantize(_ZERO),
        refunds=refunded.quantize(_ZERO),
        net=(gross - refunded).quantize(_ZERO),
        currency=str(currency),
        others={
            str(code): (total - refunds[code]).quantize(_ZERO)
            for code, (_, total) in per.items()
            if code != currency
        },
    )


def net_by_order(order_ids, *, currency: str = '') -> dict[str, Decimal]:
    """Net sales of each listed order that counts, keyed by its id as text;
    only the orders in ``currency`` when one is given."""
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    orders = counted(Order.objects.filter(pk__in=list(order_ids)))
    if currency:
        orders = orders.filter(total_currency=currency)
    out = {str(pk): Decimal(str(total or 0)) for pk, total in orders.values_list('pk', 'total')}
    for row in _refunds_by(orders, 'order_id'):
        key = str(row['order_id'])
        if key in out:
            out[key] -= Decimal(str(row['s'] or 0))
    return {key: value.quantize(_ZERO) for key, value in out.items()}


def net_by_day(qs, tz) -> dict[date, tuple[int, Decimal]]:
    """``{day: (orders, net)}`` for the counted orders in ``qs``, by the day
    each was placed on the ``tz`` clock, in :func:`net_sales`' currency."""
    currency = net_sales(qs).currency
    orders = counted(qs).filter(total_currency=currency)
    nets = net_by_order(orders.values_list('pk', flat=True))
    out: dict = {}
    for pk, placed_at in orders.values_list('pk', 'placed_at'):
        day = placed_at.astimezone(tz).date()
        n, total = out.get(day, (0, _ZERO))
        out[day] = (n + 1, total + nets.get(str(pk), _ZERO))
    return out


@dataclass
class CustomerSales:
    """What one customer bought: their counted orders and net sales, in the
    currency most of their orders carry, and when they last ordered."""

    orders: int
    net: Decimal
    currency: str
    last_order_at: datetime | None


def by_customer(customer_ids=None) -> dict[str, CustomerSales]:
    """``{customer pk as text: CustomerSales}`` for the listed customers (default:
    every customer with an order that counts). A customer with none is absent."""
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    qs = Order.objects.filter(customer__isnull=False)
    if customer_ids is not None:
        qs = qs.filter(customer_id__in=list(customer_ids))
    orders = counted(qs)
    refunds = {
        (row['order__customer_id'], row['order__total_currency']): Decimal(str(row['s'] or 0))
        for row in _refunds_by(orders, 'order__customer_id', 'order__total_currency')
    }
    best: dict = {}
    last: dict = {}
    for row in orders.values('customer_id', 'total_currency').annotate(
        n=Count('id'), t=Sum('total'), last=Max('placed_at')
    ):
        key = str(row['customer_id'])
        if row['last'] is not None and (key not in last or row['last'] > last[key]):
            last[key] = row['last']
        kept = best.get(key)
        if kept is None or (row['n'], str(row['total_currency'])) > (
            kept['n'],
            str(kept['total_currency']),
        ):
            best[key] = row
    return {
        key: CustomerSales(
            orders=row['n'],
            net=(
                Decimal(str(row['t'] or 0))
                - refunds.get((row['customer_id'], row['total_currency']), _ZERO)
            ).quantize(_ZERO),
            currency=str(row['total_currency']),
            last_order_at=last.get(key),
        )
        for key, row in best.items()
    }

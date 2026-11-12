"""Shipping agent tools."""

from __future__ import annotations

from morpheus.core import ToolError, ToolResult, tool


@tool(
    name='shipping.list_zones',
    description='List shipping zones (geographic groups + their rates).',
    scopes=['shipping.read'],
    schema={'type': 'object', 'properties': {}},
)
def list_zones_tool() -> ToolResult:
    from plugins.installed.shipping.models import ShippingZone
    from plugins.installed.shipping.rates import describe

    out = []
    for zone in ShippingZone.objects.prefetch_related('rates').all()[:50]:
        out.append(
            {
                'name': zone.name,
                'countries': zone.countries,
                'regions': zone.regions,
                'rates': [
                    {
                        'name': r.name,
                        'computation': r.computation,
                        'flat': str(r.flat_amount.amount) if r.flat_amount else None,
                        'charges': describe(r),
                        'is_active': r.is_active,
                    }
                    for r in zone.rates.all()
                ],
            }
        )
    return ToolResult(output={'zones': out})


@tool(
    name='shipping.add_flat_rate',
    description='Create a flat-fee shipping rate in a zone.',
    scopes=['shipping.write'],
    schema={
        'type': 'object',
        'properties': {
            'zone_name': {'type': 'string'},
            'name': {'type': 'string', 'description': 'Rate name (e.g. "Standard ground")'},
            'amount': {'type': 'number'},
            'currency': {
                'type': 'string',
                'description': "ISO code; leave it out to use the store's currency.",
            },
        },
        'required': ['zone_name', 'name', 'amount'],
    },
    requires_approval=True,
)
def add_flat_rate_tool(
    *, zone_name: str, name: str, amount: float, currency: str = ''
) -> ToolResult:
    from decimal import Decimal

    from djmoney.money import Money

    from plugins.installed.shipping.models import ShippingRate, ShippingZone
    from plugins.installed.shipping.rates import store_currency

    zone = ShippingZone.objects.filter(name=zone_name).first()
    if zone is None:
        raise ToolError(f'Unknown shipping zone: {zone_name}')
    rate = ShippingRate.objects.create(
        zone=zone,
        name=name[:120],
        computation='flat',
        flat_amount=Money(Decimal(str(amount)), (currency or store_currency()).upper()[:3]),
    )
    return ToolResult(
        output={'rate_id': str(rate.id), 'zone': zone.name, 'name': rate.name},
        display=f'Added rate {rate.name} to {zone.name}',
    )


@tool(
    name='shipping.set_rate',
    description=(
        'Create a shipping rate in a zone, or change the one with that name: a flat fee, '
        'free over an order amount, weight tiers (kg) or order-total tiers, or pickup '
        "(free or a fee). Amounts are in the store's currency. The rate's pricing is "
        'replaced as a whole; leave out description, days, priority or active to keep them.'
    ),
    scopes=['shipping.write'],
    schema={
        'type': 'object',
        'properties': {
            'zone_name': {'type': 'string'},
            'name': {'type': 'string', 'description': 'Rate name (e.g. "Standard")'},
            'computation': {
                'type': 'string',
                'enum': ['flat', 'free_over', 'weight_tier', 'order_total_tier', 'pickup'],
            },
            'price': {
                'type': 'number',
                'description': 'Flat fee, the price below free_over, or the pickup fee.',
            },
            'free_over': {'type': 'number', 'description': 'free_over only: free from this.'},
            'tiers': {
                'type': 'array',
                'description': 'Tiered kinds: each tier applies from `from` (kg or amount); '
                'the first starts at 0.',
                'items': {
                    'type': 'object',
                    'properties': {'from': {'type': 'number'}, 'price': {'type': 'number'}},
                    'required': ['from', 'price'],
                },
            },
            'days_min': {'type': 'integer'},
            'days_max': {'type': 'integer'},
            'description': {'type': 'string'},
            'priority': {'type': 'integer', 'description': 'Lower is shown first.'},
            'active': {'type': 'boolean'},
        },
        'required': ['zone_name', 'name', 'computation'],
    },
    requires_approval=True,
)
def set_rate_tool(  # noqa: PLR0913
    *,
    zone_name: str,
    name: str,
    computation: str,
    price: float | None = None,
    free_over: float | None = None,
    tiers: list | None = None,
    days_min: int | None = None,
    days_max: int | None = None,
    description: str | None = None,
    priority: int | None = None,
    active: bool | None = None,
) -> ToolResult:
    from plugins.installed.shipping.models import ShippingRate, ShippingZone
    from plugins.installed.shipping.rates import (
        PRICED_KINDS,
        RateError,
        describe,
        rate_values,
    )
    from plugins.installed.shipping.rates import priority as parse_priority

    if computation not in PRICED_KINDS:
        raise ToolError('A carrier-quoted rate is set up on the Shipping page.')
    zone = ShippingZone.objects.filter(name__iexact=(zone_name or '').strip()).first()
    if zone is None:
        raise ToolError(f'Unknown shipping zone: {zone_name}')
    name = (name or '').strip()[:120]
    if not name:
        raise ToolError('A rate needs a name.')
    rate = ShippingRate.objects.filter(zone=zone, name__iexact=name).first()
    try:
        values = rate_values(
            computation=computation,
            flat_amount=price,
            free_threshold=free_over,
            tiers=[((t or {}).get('from'), (t or {}).get('price')) for t in tiers or []],
            estimated_days_min=days_min
            if days_min is not None
            else getattr(rate, 'estimated_days_min', None),
            estimated_days_max=days_max
            if days_max is not None
            else getattr(rate, 'estimated_days_max', None),
        )
        if priority is not None:
            values['priority'] = parse_priority(priority)
    except RateError as exc:
        raise ToolError(str(exc)) from None
    if description is not None:
        values['description'] = description.strip()[:240]
    if active is not None:
        values['is_active'] = bool(active)
    created = rate is None
    if created:
        rate = ShippingRate(zone=zone, name=name)
    for field, value in values.items():
        setattr(rate, field, value)
    rate.save()
    return ToolResult(
        output={
            'rate_id': str(rate.id),
            'zone': zone.name,
            'name': rate.name,
            'created': created,
            'charges': describe(rate),
            'active': rate.is_active,
        },
        display=f'{"Added" if created else "Updated"} rate {rate.name} in {zone.name}: {describe(rate)}',
    )


@tool(
    name='shipping.buy_label',
    description=(
        "Buy a carrier label (Shippo or EasyPost, at the rate the Shipping page's label setting picks) for an order's parcel. "
        'Give `parcel` (an id from orders.get) for a recorded parcel, or leave it out to buy '
        'one label for everything still open and record that parcel. The carrier charges '
        "the store's account; the buyer gets the tracking by email."
    ),
    scopes=['shipping.write'],
    schema={
        'type': 'object',
        'properties': {
            'order_number': {'type': 'string'},
            'parcel': {'type': 'string', 'description': 'A recorded parcel (fulfilment) id.'},
            'provider': {'type': 'string', 'enum': ['shippo', 'easypost']},
        },
        'required': ['order_number'],
    },
    requires_approval=True,
)
def buy_label_tool(*, order_number: str, parcel: str = '', provider: str = '') -> ToolResult:
    from plugins.installed.orders.models import Order
    from plugins.installed.shipping.labels import (
        LabelError,
        label_for_parcel,
        parcel_on,
        ship_with_label,
    )

    order = Order.objects.filter(order_number=order_number).first()
    if order is None:
        raise ToolError(f'order not found: {order_number}')
    try:
        if parcel:
            found = parcel_on(order, parcel)
            if found is None:
                raise ToolError(f'no parcel {parcel} on order #{order_number}')
            label = label_for_parcel(found, provider=provider or None)
        else:
            label = ship_with_label(order, provider=provider or None)
    except LabelError as exc:
        raise ToolError(str(exc)) from None
    return ToolResult(
        output={
            'order_number': order.order_number,
            'parcel': str(label.fulfillment_id or ''),
            'provider': label.provider,
            'carrier': label.carrier,
            'service': label.service,
            'tracking_number': label.tracking_number,
            'label_url': label.label_url,
            'cost': f'{label.cost_amount} {label.cost_currency}' if label.cost_amount else '',
        },
        display=f'#{order.order_number}: {label.get_provider_display()} label'
        + (f', tracking {label.tracking_number}' if label.tracking_number else ''),
    )

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
            'currency': {'type': 'string', 'default': 'USD'},
        },
        'required': ['zone_name', 'name', 'amount'],
    },
    requires_approval=True,
)
def add_flat_rate_tool(
    *, zone_name: str, name: str, amount: float, currency: str = 'USD'
) -> ToolResult:
    from decimal import Decimal

    from djmoney.money import Money

    from plugins.installed.shipping.models import ShippingRate, ShippingZone

    zone = ShippingZone.objects.filter(name=zone_name).first()
    if zone is None:
        raise ToolError(f'Unknown shipping zone: {zone_name}')
    rate = ShippingRate.objects.create(
        zone=zone,
        name=name[:120],
        computation='flat',
        flat_amount=Money(Decimal(str(amount)), currency),
    )
    return ToolResult(
        output={'rate_id': str(rate.id), 'zone': zone.name, 'name': rate.name},
        display=f'Added rate {rate.name} to {zone.name}',
    )

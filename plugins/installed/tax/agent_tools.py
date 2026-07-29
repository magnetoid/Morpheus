"""Tax tools for the agent layer."""

from __future__ import annotations

from morpheus.core import ToolError, ToolResult, tool


@tool(
    name='tax.list_rates',
    description='List configured tax rates by region.',
    scopes=['tax.read'],
    schema={'type': 'object', 'properties': {}},
)
def list_rates_tool() -> ToolResult:
    from plugins.installed.tax.models import TaxRate

    rows = list(TaxRate.objects.select_related('region', 'category').all()[:200])
    return ToolResult(
        output={
            'rates': [
                {
                    'region': str(r.region),
                    'name': r.name,
                    'percent': str(r.rate_percent),
                    'category': r.category_id or '',
                }
                for r in rows
            ],
        },
        display=f'{len(rows)} tax rate(s)',
    )


@tool(
    name='tax.set_rate',
    description='Create or update a tax rate for a region (and optional category).',
    scopes=['tax.write'],
    schema={
        'type': 'object',
        'properties': {
            'country': {'type': 'string', 'description': 'ISO-3166 alpha-2'},
            'region': {'type': 'string', 'description': 'Subdivision code (optional)'},
            'rate_percent': {'type': 'number'},
            'name': {'type': 'string'},
            'category_code': {'type': 'string'},
        },
        'required': ['country', 'rate_percent', 'name'],
    },
    requires_approval=True,
)
def set_rate_tool(
    *,
    country: str,
    rate_percent: float,
    name: str,
    region: str = '',
    category_code: str = '',
) -> ToolResult:
    from plugins.installed.tax.models import TaxCategory, TaxRate, TaxRegion

    region_obj, _ = TaxRegion.objects.get_or_create(
        country=country.upper()[:2],
        region=(region or '').upper()[:10],
        defaults={'name': f'{country}{("-" + region) if region else ""}'},
    )
    category = None
    if category_code:
        category = TaxCategory.objects.filter(code=category_code).first()
        if not category:
            raise ToolError(f'Unknown tax category: {category_code}')
    rate, created = TaxRate.objects.update_or_create(
        region=region_obj,
        category=category,
        defaults={'name': name[:120], 'rate_percent': rate_percent},
    )
    return ToolResult(
        output={'rate_id': str(rate.id), 'percent': str(rate.rate_percent), 'created': created},
        display=f'{"Created" if created else "Updated"} {rate.name}',
    )

"""Tax tools for the agent layer."""

from __future__ import annotations

from morpheus.core import ToolError, ToolResult, tool


@tool(
    name='tax.list_rates',
    description=(
        'List the tax rates by region, the tax categories with how many products '
        'each holds, and the tax settings.'
    ),
    scopes=['tax.read'],
    schema={'type': 'object', 'properties': {}},
)
def list_rates_tool() -> ToolResult:
    from django.db.models import Count

    from plugins.installed.tax.models import TaxCategory, TaxConfiguration, TaxRate

    rows = list(TaxRate.objects.select_related('region', 'category').all()[:200])
    categories = TaxCategory.objects.annotate(products=Count('product_links'))
    config = TaxConfiguration.objects.first()
    return ToolResult(
        output={
            'rates': [
                {
                    'region': str(r.region),
                    'name': r.name,
                    'percent': str(r.rate_percent),
                    'category': r.category_id or '',
                    'compound': r.is_compound,
                    'priority': r.priority,
                }
                for r in rows
            ],
            'categories': [
                {'code': c.code, 'name': c.name, 'products': c.products} for c in categories
            ],
            'settings': {
                'provider': config.provider if config else 'local',
                'prices_include_tax': bool(config and config.prices_include_tax),
                'shipping_taxable': bool(config and config.shipping_taxable),
            },
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


@tool(
    name='tax.set_category',
    description=(
        'Create a tax category (such as books or food) or rename one. Give it rates '
        'with tax.set_rate and put products in it with tax.set_product_category.'
    ),
    scopes=['tax.write'],
    schema={
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'code': {'type': 'string', 'description': 'Short id; made from the name when empty'},
            'description': {'type': 'string'},
        },
        'required': ['name'],
    },
    requires_approval=True,
)
def set_category_tool(*, name: str, code: str = '', description: str = '') -> ToolResult:
    from plugins.installed.tax.services import set_category

    try:
        category, created = set_category(code, name, description)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    return ToolResult(
        output={'code': category.code, 'name': category.name, 'created': created},
        display=f'{"Created" if created else "Updated"} tax category {category.name}',
    )


@tool(
    name='tax.set_product_category',
    description=(
        "Put a product in a tax category, so it pays that category's rates; an empty "
        'category_code puts it back on the standard rates.'
    ),
    scopes=['tax.write'],
    schema={
        'type': 'object',
        'properties': {
            'product_id': {'type': 'string'},
            'sku': {'type': 'string'},
            'category_code': {'type': 'string'},
        },
        'required': ['category_code'],
    },
    requires_approval=True,
)
def set_product_category_tool(
    *, category_code: str, product_id: str = '', sku: str = ''
) -> ToolResult:
    from plugins.installed.catalog.models import Product
    from plugins.installed.tax.services import set_product_category

    product = None
    if product_id:
        product = Product.objects.filter(pk=product_id).first()
    elif sku:
        product = Product.objects.filter(sku=sku).first()
    if product is None:
        raise ToolError('Product not found: give product_id or sku.')
    try:
        category = set_product_category(product, category_code)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    label = category.name if category else 'standard rates'
    return ToolResult(
        output={'product_id': str(product.id), 'category_code': category.code if category else ''},
        display=f'{product.name}: {label}',
    )


@tool(
    name='tax.update_settings',
    description=(
        'Change how tax is charged: provider ("local" rates or "none"), whether '
        'product prices already include tax, and whether shipping is taxed. Omitted '
        'settings stay as they are.'
    ),
    scopes=['tax.write'],
    schema={
        'type': 'object',
        'properties': {
            'provider': {'type': 'string', 'enum': ['local', 'none']},
            'prices_include_tax': {'type': 'boolean'},
            'shipping_taxable': {'type': 'boolean'},
        },
    },
    requires_approval=True,
)
def update_settings_tool(
    *,
    provider: str | None = None,
    prices_include_tax: bool | None = None,
    shipping_taxable: bool | None = None,
) -> ToolResult:
    from plugins.installed.tax.services import update_settings

    try:
        config = update_settings(
            provider=provider,
            prices_include_tax=prices_include_tax,
            shipping_taxable=shipping_taxable,
        )
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    return ToolResult(
        output={
            'provider': config.provider,
            'prices_include_tax': config.prices_include_tax,
            'shipping_taxable': config.shipping_taxable,
        },
        display='Tax settings saved',
    )

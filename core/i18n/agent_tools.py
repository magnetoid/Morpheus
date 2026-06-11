"""Translation agent tools."""

from __future__ import annotations

from core.agents import ToolError, ToolResult, tool


@tool(
    name='i18n.translate_product',
    description="Set translations for a product's fields in a language.",
    scopes=['catalog.write'],
    schema={
        'type': 'object',
        'properties': {
            'slug': {'type': 'string'},
            'language_code': {'type': 'string', 'description': 'BCP-47 short code, e.g. "es"'},
            'name': {'type': 'string'},
            'short_description': {'type': 'string'},
            'description': {'type': 'string'},
        },
        'required': ['slug', 'language_code'],
    },
    requires_approval=True,
)
def translate_product_tool(
    *,
    slug: str,
    language_code: str,
    name: str = '',
    short_description: str = '',
    description: str = '',
) -> ToolResult:
    from core.i18n import bulk_set_translations
    from plugins.installed.catalog.models import Product

    try:
        product = Product.objects.get(slug=slug)
    except Product.DoesNotExist as e:
        raise ToolError(f'Unknown product: {slug}') from e
    n = bulk_set_translations(
        product,
        language_code,
        {'name': name, 'short_description': short_description, 'description': description},
    )
    return ToolResult(
        output={'product': slug, 'language': language_code, 'fields': n},
        display=f'Set {n} field(s) for {slug} in {language_code}',
    )


@tool(
    name='i18n.list_translations',
    description='Show all translations stored for a product (by slug).',
    scopes=['catalog.read'],
    schema={
        'type': 'object',
        'properties': {'slug': {'type': 'string'}},
        'required': ['slug'],
    },
)
def list_translations_tool(*, slug: str) -> ToolResult:
    from core.i18n import translations_for
    from plugins.installed.catalog.models import Product

    try:
        product = Product.objects.get(slug=slug)
    except Product.DoesNotExist as e:
        raise ToolError(f'Unknown product: {slug}') from e
    return ToolResult(output={'product': slug, 'translations': translations_for(product)})

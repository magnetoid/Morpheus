"""Wishlist agent tools."""

from __future__ import annotations

from core.agents import ToolError, ToolResult, tool


@tool(
    name='wishlist.add',
    description="Add a product to the active visitor's wishlist by slug.",
    scopes=['wishlist.write'],
    schema={
        'type': 'object',
        'properties': {'slug': {'type': 'string'}},
        'required': ['slug'],
    },
)
def add_to_wishlist_tool(*, slug: str, context: dict | None = None) -> ToolResult:
    from plugins.installed.catalog.models import Product
    from plugins.installed.wishlist.services import add_item, get_or_create_wishlist

    request = (context or {}).get('request')
    customer = (context or {}).get('customer')
    if request is None and customer is None:
        raise ToolError('No request/customer in context.')
    session_key = getattr(getattr(request, 'session', None), 'session_key', '') if request else ''
    wishlist = get_or_create_wishlist(customer=customer, session_key=session_key)
    if wishlist is None:
        raise ToolError('Could not resolve wishlist.')
    try:
        product = Product.objects.get(slug=slug, status='active')
    except Product.DoesNotExist as e:
        raise ToolError(f'Unknown product: {slug}') from e
    add_item(wishlist=wishlist, product=product)
    return ToolResult(
        output={
            'wishlist_id': str(wishlist.id),
            'product': product.name,
            'item_count': wishlist.item_count,
        },
        display=f'Added {product.name} to wishlist',
    )


@tool(
    name='wishlist.summary',
    description="Show items in the active visitor's wishlist.",
    scopes=['wishlist.read'],
    schema={'type': 'object', 'properties': {}},
)
def wishlist_summary_tool(*, context: dict | None = None) -> ToolResult:
    from plugins.installed.wishlist.services import get_or_create_wishlist

    request = (context or {}).get('request')
    customer = (context or {}).get('customer')
    session_key = getattr(getattr(request, 'session', None), 'session_key', '') if request else ''
    wishlist = get_or_create_wishlist(customer=customer, session_key=session_key)
    if wishlist is None:
        return ToolResult(output={'wishlist': None})
    return ToolResult(
        output={
            'wishlist_id': str(wishlist.id),
            'name': wishlist.name,
            'items': [
                {
                    'product': i.product.name,
                    'slug': i.product.slug,
                    'added_at': i.added_at.isoformat(),
                }
                for i in wishlist.items.select_related('product').all()
            ],
        }
    )

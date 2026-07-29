"""Cart tools — agent-driven cart manipulation for the Concierge."""

from __future__ import annotations

from morpheus.core import ToolError, ToolResult, tool


def _resolve_cart(context: dict) -> object | None:
    """Get-or-create a cart from a request session, mirroring storefront behavior."""
    request = (context or {}).get('request')
    if request is None:
        return None
    try:
        from plugins.installed.orders.models import Cart
    except ImportError:
        return None
    customer = (context or {}).get('customer')
    if customer is not None and getattr(customer, 'is_authenticated', False):
        cart, _ = Cart.objects.get_or_create(customer=customer, status='active')
        return cart
    if hasattr(request, 'session'):
        if not request.session.session_key:
            request.session.save()
        cart, _ = Cart.objects.get_or_create(
            session_key=request.session.session_key,
            status='active',
        )
        return cart
    return None


@tool(
    name='cart.add_item',
    description='Add a product (by slug) to the active cart.',
    scopes=['cart.write'],
    schema={
        'type': 'object',
        'properties': {
            'slug': {'type': 'string'},
            'quantity': {'type': 'integer', 'minimum': 1, 'maximum': 20, 'default': 1},
        },
        'required': ['slug'],
    },
)
def add_to_cart_tool(*, slug: str, quantity: int = 1, context: dict | None = None) -> ToolResult:
    from plugins.installed.catalog.models import Product
    from plugins.installed.orders.models import CartItem

    cart = _resolve_cart(context or {})
    if cart is None:
        raise ToolError('No request/session available — cannot resolve cart.')
    try:
        product = Product.objects.get(slug=slug, status='active')
    except Product.DoesNotExist as e:
        raise ToolError(f'Unknown product: {slug}') from e
    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': quantity, 'unit_price': product.price},
    )
    if not created:
        item.quantity = min(20, item.quantity + max(1, int(quantity)))
        item.save(update_fields=['quantity'])
    return ToolResult(
        output={
            'cart_id': str(cart.id),
            'item': {'product': product.name, 'quantity': item.quantity},
        },
        display=f'Added {item.quantity}× {product.name}',
    )


@tool(
    name='cart.summary',
    description='Return a summary of the active cart: items, quantities, subtotal.',
    scopes=['cart.read'],
    schema={'type': 'object', 'properties': {}},
)
def get_cart_summary_tool(*, context: dict | None = None) -> ToolResult:
    cart = _resolve_cart(context or {})
    if cart is None:
        return ToolResult(output={'cart': None})
    items = [
        {
            'product': i.product.name,
            'slug': i.product.slug,
            'quantity': i.quantity,
            'unit_price': str(getattr(i.unit_price, 'amount', '')),
        }
        for i in cart.items.select_related('product')
    ]
    return ToolResult(
        output={
            'cart_id': str(cart.id),
            'items': items,
            'item_count': sum(i['quantity'] for i in items),
        }
    )

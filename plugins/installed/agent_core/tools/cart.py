"""Cart tools — agent-driven cart manipulation for the Concierge."""

from __future__ import annotations

from morpheus.core import ToolError, ToolResult, tool


def _resolve_cart(context: dict) -> object | None:
    """The shopper's cart, found the way the storefront finds it (CartService).

    This used to query ``Cart(status='active')`` — a field Cart has never had —
    so every call raised FieldError and the concierge could not add anything.
    """
    request = (context or {}).get('request')
    if request is None:
        return None
    try:
        from plugins.installed.orders.services import CartService
    except ImportError:
        return None
    customer = (context or {}).get('customer')
    if customer is not None and getattr(customer, 'is_authenticated', False):
        cart = CartService.get_or_create_cart(customer=customer)
    elif hasattr(request, 'session'):
        if not request.session.session_key:
            request.session.save()
        cart = CartService.get_or_create_cart(session_key=request.session.session_key)
    else:
        return None
    if hasattr(request, 'session') and not request.session.get('cart_id'):
        request.session['cart_id'] = str(cart.id)
    return cart


@tool(
    # Renamed from cart.add_item to avoid a registry name-collision with the
    # ACP session tool of the same name (agentic_checkout/agent_tools.py). That
    # collision resolved by plugin load order, and THIS slug/session variant —
    # which needs a request in context — cannot run under the MCP cart cluster
    # (context={'source':'mcp'} has no request), so a reorder would have handed
    # the cart cluster an unrunnable tool. Distinct operation, distinct name.
    name='cart.add_by_slug',
    description='Add a product (by slug) to the active session cart (storefront concierge).',
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
    from plugins.installed.orders.services import CartService

    cart = _resolve_cart(context or {})
    if cart is None:
        raise ToolError('No request/session available — cannot resolve cart.')
    try:
        product = Product.objects.get(slug=slug, status='active')
    except Product.DoesNotExist as e:
        raise ToolError(f'Unknown product: {slug}') from e
    # Through CartService, like every storefront add: the price seam, the $0
    # guard, one currency per cart and the stock hold all apply here too.
    try:
        item = CartService.add_item(
            cart=cart, product_id=str(product.id), quantity=max(1, min(20, int(quantity)))
        )
    except ValueError as e:
        raise ToolError(str(e)) from e
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

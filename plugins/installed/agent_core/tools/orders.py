"""Order tools — read access for support + merchant agents."""

from __future__ import annotations

from morpheus.core import ToolError, ToolResult, tool


@tool(
    name='orders.list_recent',
    description='List the most recent orders. Limit is capped at 25.',
    scopes=['orders.read'],
    schema={
        'type': 'object',
        'properties': {
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 25, 'default': 10},
            'state': {
                'type': 'string',
                'description': (
                    'Filter by order status (e.g. pending, processing, shipped, '
                    'delivered, cancelled).'
                ),
            },
        },
    },
)
def list_recent_orders_tool(*, limit: int = 10, state: str = '') -> ToolResult:
    from plugins.installed.orders.models import Order

    limit = max(1, min(int(limit or 10), 25))
    # Order records `status` and `placed_at` — there is no state/created_at.
    qs = Order.objects.all().order_by('-placed_at')
    if state:
        qs = qs.filter(status=state)
    rows = []
    for o in qs[:limit]:
        rows.append(
            {
                'order_number': o.order_number,
                'state': o.status,
                'total': str(getattr(o.total, 'amount', '')),
                'currency': str(getattr(o.total, 'currency', '')),
                'created_at': o.placed_at.isoformat(),
                'customer_email': getattr(o.customer, 'email', '') if o.customer_id else o.email,
            }
        )
    return ToolResult(output={'orders': rows}, display=f'{len(rows)} order(s)')


@tool(
    name='orders.summary',
    description='Detailed summary of one order by order number.',
    scopes=['orders.read'],
    schema={
        'type': 'object',
        'properties': {'order_number': {'type': 'string'}},
        'required': ['order_number'],
    },
)
def summarise_order_tool(*, order_number: str) -> ToolResult:
    from plugins.installed.orders.models import Order

    try:
        order = Order.objects.prefetch_related('items').get(order_number=order_number)
    except Order.DoesNotExist as e:
        raise ToolError(f'Order not found: {order_number}') from e
    items = [
        {
            'product': i.product.name if i.product_id else i.product_name,
            'quantity': i.quantity,
            'unit_price': str(getattr(i.unit_price, 'amount', '')),
        }
        for i in order.items.all()
    ]
    return ToolResult(
        output={
            'order_number': order.order_number,
            'state': order.status,
            'total': str(getattr(order.total, 'amount', '')),
            'currency': str(getattr(order.total, 'currency', '')),
            'items': items,
            'created_at': order.placed_at.isoformat(),
        }
    )


# ─── Admin write tools — fulfill / ship / cancel / mark refunded ──────────────


def _serialize_admin(order) -> dict:
    return {
        'order_number': order.order_number,
        'status': order.status,
        'payment_status': order.payment_status,
        'tracking_number': order.tracking_number or '',
    }


@tool(
    name='orders.mark_fulfilled',
    description='Mark a paid/processing order as fulfilled (uses the Order FSM).',
    scopes=['orders.write'],
    schema={
        'type': 'object',
        'properties': {'order_number': {'type': 'string'}},
        'required': ['order_number'],
    },
)
def mark_order_fulfilled_tool(*, order_number: str) -> ToolResult:
    from django_fsm import TransitionNotAllowed

    from plugins.installed.orders.models import Order

    order = Order.objects.filter(order_number=order_number).first()
    if order is None:
        raise ToolError(f'order {order_number!r} not found')
    try:
        order.fulfill()
        order.save()
    except TransitionNotAllowed as e:
        raise ToolError(f'cannot fulfill from status={order.status}: {e}') from None
    return ToolResult(
        output=_serialize_admin(order), display=f'#{order.order_number} → {order.status}'
    )


@tool(
    name='orders.mark_shipped',
    description='Mark a fulfilled order as shipped, optionally with a tracking number.',
    scopes=['orders.write'],
    schema={
        'type': 'object',
        'properties': {
            'order_number': {'type': 'string'},
            'tracking_number': {'type': 'string', 'default': ''},
        },
        'required': ['order_number'],
    },
)
def mark_order_shipped_tool(*, order_number: str, tracking_number: str = '') -> ToolResult:
    from django_fsm import TransitionNotAllowed

    from plugins.installed.orders.models import Order

    order = Order.objects.filter(order_number=order_number).first()
    if order is None:
        raise ToolError(f'order {order_number!r} not found')
    try:
        order.ship(tracking_number=tracking_number)
        order.save()
    except TransitionNotAllowed as e:
        raise ToolError(f'cannot ship from status={order.status}: {e}') from None
    return ToolResult(
        output=_serialize_admin(order),
        display=f'#{order.order_number} shipped'
        + (f' ({tracking_number})' if tracking_number else ''),
    )


# orders.cancel migrated to plugins/installed/orders/agent_tools.py (the richer
# confirmed+staging version there is now the single canonical owner; the Worker
# resolves 'orders.cancel' by name from the registry). Boundary/dedup: #23-plan
# Phase 1. agent_core keeps its distinct mark_fulfilled/shipped/refunded tools.


@tool(
    name='orders.mark_refunded',
    description=(
        'Flag an order as refunded — manual, for refunds processed outside '
        'Morpheus (e.g. directly in Stripe / bank). The FSM has no '
        'refund() transition because the canonical refund happens in the '
        'payments plugin; this just lets the merchant flag the row.'
    ),
    scopes=['orders.write'],
    schema={
        'type': 'object',
        'properties': {
            'order_number': {'type': 'string'},
            'reason': {'type': 'string', 'default': ''},
        },
        'required': ['order_number'],
    },
    requires_approval=True,
)
def mark_order_refunded_tool(*, order_number: str, reason: str = '') -> ToolResult:
    from plugins.installed.orders.models import Order

    order = Order.objects.filter(order_number=order_number).first()
    if order is None:
        raise ToolError(f'order {order_number!r} not found')
    Order.objects.filter(pk=order.pk).update(
        status='refunded',
        payment_status='refunded',
    )
    order.refresh_from_db()
    order.log_event('ORDER_REFUNDED', message=reason)
    return ToolResult(output=_serialize_admin(order), display=f'#{order.order_number} refunded')

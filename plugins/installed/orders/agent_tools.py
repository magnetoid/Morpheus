"""Order-side agent tools (search/get + refunds + RMA).

The read tools (orders.search / orders.get) were migrated here from
core/assistant/tools/ecommerce.py so the Order model queries live in the plugin
that owns them. Tool names are unchanged — Linda sources them by name from the
agent registry, so her prompts/skills keep resolving.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from djmoney.money import Money

from core.agents import ToolError, ToolResult, tool


def _money_str(value) -> str:
    """Render a Money / Decimal / numeric amount as a plain decimal string."""
    if value is None:
        return ''
    amount = getattr(value, 'amount', value)
    try:
        return str(Decimal(str(amount)))
    except Exception:  # noqa: BLE001
        return ''


@tool(
    name='orders.search',
    description=(
        'Search orders. Filter by status (pending/confirmed/processing/'
        'fulfilled/shipped/delivered/cancelled/refunded), date range '
        '(days_back), customer email substring, or order_number prefix. '
        'Returns up to `limit` orders, newest first.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'status': {'type': 'string'},
            'days_back': {'type': 'integer', 'minimum': 1, 'maximum': 365},
            'email': {'type': 'string'},
            'order_number': {'type': 'string'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20},
        },
    },
)
def orders_search_tool(
    *,
    status: str = '',
    days_back: int = 0,
    email: str = '',
    order_number: str = '',
    limit: int = 20,
) -> ToolResult:
    from django.utils import timezone

    from plugins.installed.orders.models import Order

    qs = Order.objects.select_related('customer').all()
    if status:
        qs = qs.filter(status=status)
    if days_back:
        qs = qs.filter(placed_at__gte=timezone.now() - timedelta(days=int(days_back)))
    if email:
        qs = qs.filter(email__icontains=email)
    if order_number:
        qs = qs.filter(order_number__icontains=order_number)
    qs = qs.order_by('-placed_at')[: max(1, min(int(limit or 20), 50))]
    rows = [
        {
            'order_number': o.order_number,
            'status': o.status,
            'payment_status': getattr(o, 'payment_status', ''),
            'total': _money_str(getattr(o, 'total', None)),
            'currency': str(getattr(getattr(o, 'total', None), 'currency', '')),
            'email': o.email or getattr(o.customer, 'email', '') if o.customer_id else o.email,
            'placed_at': o.placed_at.isoformat() if o.placed_at else '',
        }
        for o in qs
    ]
    return ToolResult(output={'orders': rows, 'count': len(rows)}, display=f'{len(rows)} order(s)')


@tool(
    name='orders.get',
    description=(
        'Fetch a single order by `order_number` with line items, '
        'refunds, fulfillments, and customer info.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {'order_number': {'type': 'string'}},
        'required': ['order_number'],
    },
)
def orders_get_tool(*, order_number: str) -> ToolResult:
    from plugins.installed.orders.models import Order

    try:
        o = (
            Order.objects.select_related('customer')
            .prefetch_related('items', 'refunds', 'fulfillments')
            .get(order_number=order_number)
        )
    except Order.DoesNotExist:
        raise ToolError(f'order not found: {order_number}')  # noqa: B904
    items = [
        {
            'name': i.product_name,
            'sku': i.sku,
            'quantity': i.quantity,
            'unit_price': _money_str(i.unit_price),
            'total_price': _money_str(i.total_price),
            'fulfilled_quantity': getattr(i, 'fulfilled_quantity', 0),
        }
        for i in o.items.all()
    ]
    refunds = [
        {
            'amount': _money_str(getattr(r, 'amount', None)),
            'reason': getattr(r, 'reason', ''),
            'created_at': r.created_at.isoformat() if getattr(r, 'created_at', None) else '',
        }
        for r in (getattr(o, 'refunds', None).all() if hasattr(o, 'refunds') else [])
    ]
    fulfillments = [
        {
            'state': getattr(f, 'state', ''),
            'tracking_number': getattr(f, 'tracking_number', ''),
            'carrier': getattr(f, 'carrier', ''),
            'created_at': f.created_at.isoformat() if getattr(f, 'created_at', None) else '',
        }
        for f in (getattr(o, 'fulfillments', None).all() if hasattr(o, 'fulfillments') else [])
    ]
    return ToolResult(
        output={
            'order_number': o.order_number,
            'status': o.status,
            'payment_status': getattr(o, 'payment_status', ''),
            'total': _money_str(getattr(o, 'total', None)),
            'subtotal': _money_str(getattr(o, 'subtotal', None)),
            'tax': _money_str(getattr(o, 'tax', None)),
            'shipping': _money_str(getattr(o, 'shipping', None)),
            'discount': _money_str(getattr(o, 'discount', None)),
            'currency': str(getattr(getattr(o, 'total', None), 'currency', '')),
            'email': o.email or (o.customer.email if o.customer_id else ''),
            'customer_id': str(o.customer_id) if o.customer_id else '',
            'placed_at': o.placed_at.isoformat() if o.placed_at else '',
            'notes': getattr(o, 'notes', '') or '',
            'items': items,
            'refunds': refunds,
            'fulfillments': fulfillments,
        }
    )


@tool(
    name='orders.refund',
    description='Refund (all or part of) an order through the payment provider.',
    scopes=['orders.write'],
    schema={
        'type': 'object',
        'properties': {
            'order_number': {'type': 'string'},
            'amount': {'type': 'number', 'description': 'Refund amount; omit for full refund.'},
            'reason': {
                'type': 'string',
                'enum': [
                    'customer_request',
                    'defective',
                    'not_as_described',
                    'wrong_item',
                    'other',
                ],
                'default': 'customer_request',
            },
            'notes': {'type': 'string'},
        },
        'required': ['order_number'],
    },
    requires_approval=True,
)
def refund_order_tool(
    *,
    order_number: str,
    amount: float | None = None,
    reason: str = 'customer_request',
    notes: str = '',
) -> ToolResult:
    from plugins.installed.orders.models import Order
    from plugins.installed.orders.refunds import RefundService

    try:
        order = Order.objects.get(order_number=order_number)
    except Order.DoesNotExist as e:
        raise ToolError(f'Unknown order: {order_number}') from e

    refund_amount = (
        order.total
        if amount is None
        else Money(
            Decimal(str(amount)),
            str(order.total.currency),
        )
    )
    refund = RefundService.process(
        order=order,
        amount=refund_amount,
        reason=reason,
        notes=notes,
    )
    return ToolResult(
        output={
            'refund_id': str(refund.id),
            'order_number': order.order_number,
            'amount': str(refund.amount.amount),
            'currency': str(refund.amount.currency),
            'processed': refund.is_processed,
        },
        display=f'Refund {refund_amount} on order #{order.order_number}',
    )


@tool(
    name='returns.list',
    description='List recent return requests, optionally filtered by state.',
    scopes=['orders.read'],
    schema={
        'type': 'object',
        'properties': {
            'state': {
                'type': 'string',
                'enum': [
                    'requested',
                    'approved',
                    'rejected',
                    'received',
                    'refunded',
                    'cancelled',
                ],
            },
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20},
        },
    },
)
def list_returns_tool(*, state: str = '', limit: int = 20) -> ToolResult:
    from plugins.installed.orders.refunds import ReturnRequest

    qs = ReturnRequest.objects.all().order_by('-created_at')
    if state:
        qs = qs.filter(state=state)
    rows = list(qs[: max(1, min(int(limit or 20), 50))])
    return ToolResult(
        output={
            'returns': [
                {
                    'rma': r.rma_number,
                    'order': r.order.order_number,
                    'state': r.state,
                    'reason': r.reason,
                    'item_count': len(r.items or []),
                    'created_at': r.created_at.isoformat(),
                }
                for r in rows
            ],
        }
    )


@tool(
    name='returns.approve',
    description='Approve a return request and quote a refund amount.',
    scopes=['orders.write'],
    schema={
        'type': 'object',
        'properties': {
            'rma_number': {'type': 'string'},
            'refund_amount': {
                'type': 'number',
                'description': 'Optional override of computed amount.',
            },
        },
        'required': ['rma_number'],
    },
    requires_approval=True,
)
def approve_return_tool(*, rma_number: str, refund_amount: float | None = None) -> ToolResult:
    from plugins.installed.orders.refunds import ReturnRequest, ReturnService

    try:
        rr = ReturnRequest.objects.get(rma_number=rma_number)
    except ReturnRequest.DoesNotExist as e:
        raise ToolError(f'No RMA: {rma_number}') from e
    money = None
    if refund_amount is not None:
        money = Money(Decimal(str(refund_amount)), 'USD')
    rr = ReturnService.approve(rr, refund_amount=money)
    return ToolResult(
        output={
            'rma': rr.rma_number,
            'state': rr.state,
            'refund_amount': str(rr.refund_amount.amount) if rr.refund_amount else None,
        },
        display=f'Approved {rr.rma_number}',
    )

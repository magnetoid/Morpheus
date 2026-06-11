"""Order-side agent tools (refunds + RMA)."""

from __future__ import annotations

from decimal import Decimal

from djmoney.money import Money

from core.agents import ToolError, ToolResult, tool


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

"""Agent tools for payments."""

from __future__ import annotations

from morpheus.core import ToolError, ToolResult, tool


@tool(
    name='payments.order_risk',
    description=(
        'The fraud check of one order by `order_number`: its score (0-100), level '
        '(Low, Watch, Review, High) and the reasons. Nothing holds or cancels an order '
        'because of it; orders placed before the check ran have none.'
    ),
    scopes=['orders.read'],
    schema={
        'type': 'object',
        'properties': {'order_number': {'type': 'string'}},
        'required': ['order_number'],
    },
)
def order_risk_tool(*, order_number: str) -> ToolResult:
    from plugins.installed.orders.models import Order
    from plugins.installed.payments.risk import order_risk

    order = Order.objects.filter(order_number=order_number).only('metadata').first()
    if order is None:
        raise ToolError(f'order not found: {order_number}')
    risk = order_risk(order)
    if risk is None:
        return ToolResult(
            output={'order_number': order_number, 'scored': False},
            display=f'Order {order_number} has no fraud check',
        )
    return ToolResult(
        output={'order_number': order_number, 'scored': True, **risk},
        display=f'Order {order_number}: {risk["level"]} risk, score {risk["score"]}',
    )

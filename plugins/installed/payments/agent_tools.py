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


@tool(
    name='payments.capture',
    description=(
        "Charge an order's held card payment now (the store charges cards when "
        'parcels ship or when the merchant says: payments `capture_mode`). MONEY '
        'OPERATION — after the user approves, pass confirmed=True, hard_gate_ack="YES" '
        'and echo=<the order number typed back>. Cancelling the order gives the hold '
        'back instead.'
    ),
    scopes=['orders.write'],
    schema={
        'type': 'object',
        'properties': {
            'order_number': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
            'hard_gate_ack': {'type': 'string', 'default': ''},
            'echo': {'type': 'string', 'default': ''},
        },
        'required': ['order_number'],
    },
    requires_approval=True,
)
def capture_payment_tool(
    *, order_number: str, confirmed: bool = False, hard_gate_ack: str = '', echo: str = ''
) -> ToolResult:
    from core.assistant.tools.ecommerce_writes import (  # noqa: PLC0415
        _require_confirmed,
        _require_hard_gate,
    )
    from plugins.installed.orders.models import Order
    from plugins.installed.payments.services.capture import capture_order

    _require_confirmed(confirmed)
    _require_hard_gate(hard_gate_ack=hard_gate_ack, target_name=order_number, echo=echo)
    order = Order.objects.filter(order_number=order_number).first()
    if order is None:
        raise ToolError(f'order not found: {order_number}')
    result = capture_order(order)
    if not result.get('success'):
        raise ToolError(result.get('error') or 'the payment could not be charged')
    return ToolResult(
        output={'order_number': order_number, 'charged': True, 'total': str(order.total)},
        display=f'Charged order #{order_number}.',
    )

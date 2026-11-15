"""Agent tools for draft orders."""

from __future__ import annotations

from morpheus.core import ToolError, ToolResult, tool


@tool(
    name='draft_orders.list',
    description='List recent draft orders.',
    scopes=['orders.read'],
    schema={'type': 'object', 'properties': {'limit': {'type': 'integer', 'default': 50}}},
)
def list_drafts_tool(*, limit: int = 50) -> ToolResult:
    from plugins.installed.draft_orders.models import DraftOrder

    qs = DraftOrder.objects.order_by('-created_at')[: max(1, min(limit, 200))]
    rows = [
        {
            'number': d.number,
            'status': d.status,
            'customer_email': d.customer_email,
            'total': str(d.total.amount),
            'currency': str(d.total.currency),
            'created_at': d.created_at.isoformat(),
        }
        for d in qs
    ]
    return ToolResult(output={'drafts': rows}, display=f'{len(rows)} draft order(s)')


@tool(
    name='draft_orders.convert',
    description='Convert a draft order to a real order.',
    scopes=['orders.write'],
    schema={'type': 'object', 'properties': {'number': {'type': 'string'}}, 'required': ['number']},
    requires_approval=True,
)
def convert_draft_tool(*, number: str) -> ToolResult:
    from plugins.installed.draft_orders import services
    from plugins.installed.draft_orders.models import DraftOrder

    try:
        draft = DraftOrder.objects.get(number=number)
    except DraftOrder.DoesNotExist as e:
        raise ToolError(f'No draft with number {number}') from e
    services.recalc(draft)
    order = services.convert_to_order(draft)
    return ToolResult(
        output={'order_number': order.order_number, 'order_id': str(order.id)},
        display=f'Converted draft {number} → order {order.order_number}',
    )


@tool(
    name='draft_orders.send_payment_link',
    description=(
        'Email the customer a link to pay a draft order. An open draft is converted to an '
        "order first, at the draft's prices; a converted one re-sends the link for its order."
    ),
    scopes=['orders.write'],
    schema={'type': 'object', 'properties': {'number': {'type': 'string'}}, 'required': ['number']},
    requires_approval=True,
)
def send_payment_link_tool(*, number: str) -> ToolResult:
    from plugins.installed.draft_orders import services
    from plugins.installed.draft_orders.models import DraftOrder
    from plugins.installed.payments import pay_link

    try:
        draft = DraftOrder.objects.get(number=number)
    except DraftOrder.DoesNotExist as e:
        raise ToolError(f'No draft with number {number}') from e
    try:
        order = services.send_payment_link(draft)
    except services.PaymentLinkError as e:
        raise ToolError(str(e)) from e
    return ToolResult(
        output={
            'order_number': order.order_number,
            'email': order.email,
            'pay_url': pay_link.pay_url(order),
        },
        display=f'Payment link for order {order.order_number} sent to {order.email}',
    )

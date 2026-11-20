"""Linda's withdrawal tools (v0.181.0): read the withdrawals customers sent, and
record one a customer sent another way (an email, a letter, a call).

``returns.process_withdrawal`` withdraws through the same rule as the page
(``orders.withdrawal.withdraw``), so an order none of which has left is
cancelled and paid back in full. That is a refund, so the agents' per-refund
cap applies before anything is recorded, as for ``orders.cancel``.
"""

from __future__ import annotations

from decimal import Decimal

from core.agents.guardrails import max_refund_value
from morpheus.core import ToolError, ToolResult, tool


def _row(n) -> dict:
    return {
        'id': str(n.pk),
        'order': n.order.order_number,
        'name': n.name,
        'email': n.email,
        'source': n.source,
        'submitted_at': n.submitted_at.isoformat(),
        'acknowledged_at': n.acknowledged_at.isoformat() if n.acknowledged_at else None,
        'outcome': n.outcome,
        'note': n.note,
        'return': n.return_request.rma_number if n.return_request else None,
        'lines': [
            {
                'product': line.get('product_name', ''),
                'quantity': line.get('quantity'),
                'right': line.get('right'),
                'reason': line.get('reason', ''),
            }
            for line in (n.lines or [])
        ],
    }


@tool(
    name='returns.list_withdrawals',
    description=(
        'List withdrawals from the contract that customers sent (the "Withdraw from '
        'contract here" function), newest first: who, when, the acknowledgement, and '
        'whether the order was cancelled or a return opened.'
    ),
    scopes=['orders.read'],
    schema={
        'type': 'object',
        'properties': {
            'order_number': {'type': 'string', 'description': 'Only this order.'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20},
        },
    },
)
def list_withdrawals_tool(*, order_number: str = '', limit: int = 20) -> ToolResult:
    from plugins.installed.orders.models import WithdrawalNotice  # noqa: PLC0415

    qs = WithdrawalNotice.objects.select_related('order', 'return_request')
    if order_number:
        qs = qs.filter(order__order_number__iexact=order_number.strip())
    rows = [_row(n) for n in qs[: max(1, min(int(limit or 20), 50))]]
    return ToolResult(output={'withdrawals': rows}, display=f'{len(rows)} withdrawals')


@tool(
    name='returns.process_withdrawal',
    description=(
        "Record a customer's withdrawal from the contract for an order that they sent "
        'another way (an email, a letter, a call), and act on it as the withdrawal page '
        'does: an order none of which has left is cancelled and everything paid goes back; '
        'otherwise a return opens for the goods. The customer gets the acknowledgement email.'
    ),
    scopes=['orders.write'],
    schema={
        'type': 'object',
        'properties': {
            'order_number': {'type': 'string'},
            'name': {'type': 'string', 'description': "The customer's name, as they gave it."},
            'email': {
                'type': 'string',
                'description': "Where the acknowledgement goes; the order's email if left out.",
            },
        },
        'required': ['order_number', 'name'],
    },
    requires_approval=True,
)
def process_withdrawal_tool(
    *, order_number: str, name: str, email: str = '', context: dict | None = None
) -> ToolResult:
    from plugins.installed.orders.models import Order  # noqa: PLC0415
    from plugins.installed.orders.withdrawal import (  # noqa: PLC0415
        WithdrawalRefused,
        preview,
        withdraw,
    )
    from plugins.installed.returns_portal import withdrawal  # noqa: PLC0415

    order = Order.objects.filter(order_number__iexact=(order_number or '').strip()).first()
    if order is None:
        raise ToolError(f'No order {order_number}')
    plan = preview(order, days=withdrawal.days())
    cap = max_refund_value()
    refund = plan['refund']
    if refund is not None and cap and refund.amount > Decimal(str(cap)):
        raise ToolError(
            f'withdrawing from order #{order.order_number} would pay back {refund}, over the '
            f'{cap:g} {refund.currency} per-refund cap; record it from the order page or '
            'raise the cap in Settings → Agent guardrails'
        )
    actor = (context or {}).get('user')
    try:
        notice = withdraw(
            order,
            name=name,
            email=(email or order.email),
            days=withdrawal.days(),
            actor=actor,
            source='staff',
        )
    except WithdrawalRefused as e:
        raise ToolError(str(e)) from e
    return ToolResult(
        output=_row(notice),
        display=f'Withdrawal from #{order.order_number} recorded: {notice.note}',
    )

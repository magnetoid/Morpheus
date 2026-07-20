"""Order-side agent tools (search/get + refunds + RMA + write ops).

The read tools (orders.search / orders.get) and the write tools
(orders.update_status / orders.cancel / orders.add_note / orders.refund) were
migrated here from core/assistant/tools/{ecommerce,ecommerce_writes,admin_ops}.py
so the Order model queries live in the plugin that owns them (core-boundary
ratchet). Tool names/scopes/gates are unchanged — Linda sources them by name
from the agent registry, so her prompts/skills keep resolving, and the shared
confirm/staging/hard-gate helpers stay in core (imported below; plugin→core is
the allowed direction).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from djmoney.money import Money

from core.agents import ToolError, ToolResult, tool

# Shared write-gate helpers stay in core (imported by metafields/cms/workflows
# too); plugin→core is the allowed import direction, so this is not a leak.
from core.assistant.tools.ecommerce_writes import (
    _is_staged,
    _obj_ref,
    _require_confirmed,
    _require_hard_gate,
    _stage,
)
from core.money import money_str as _money_str

# Target status → the Order FSM transition method that reaches it. Statuses with
# no entry (e.g. 'refunded', 'pending') aren't reachable via a status poke —
# refunds route through the refund service.
_ORDER_TRANSITIONS = {
    'confirmed': 'confirm',
    'processing': 'process',
    'fulfilled': 'fulfill',
    'shipped': 'ship',
    'delivered': 'deliver',
    'cancelled': 'cancel',
}


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
    description=(
        'Refund all or part of an order through the payment provider. MONEY '
        'OPERATION — after the user approves, pass confirmed=True, '
        'hard_gate_ack="YES", and echo=<the order number typed back>. Omit '
        '`amount` for a full refund.'
    ),
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
            'notes': {'type': 'string', 'default': ''},
            'confirmed': {'type': 'boolean', 'default': False},
            'hard_gate_ack': {'type': 'string', 'default': ''},
            'echo': {'type': 'string', 'default': ''},
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
    confirmed: bool = False,
    hard_gate_ack: str = '',
    echo: str = '',
) -> ToolResult:
    # Money op: two-step confirm + hard gate (ack + echo the order number back).
    # Migrated from core admin_ops.py with the gate intact — a refund must keep
    # its audit trail (record_ai_decision fires inside _require_hard_gate).
    _require_confirmed(confirmed)
    _require_hard_gate(hard_gate_ack=hard_gate_ack, target_name=order_number, echo=echo)
    from plugins.installed.orders.models import Order
    from plugins.installed.orders.refunds import RefundService

    order = Order.objects.filter(order_number=order_number).first()
    if order is None:
        raise ToolError(f'unknown order: {order_number}')
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
            'processed': getattr(refund, 'is_processed', None),
        },
        display=f'Refunded {refund_amount} on order #{order.order_number}.',
    )


@tool(
    name='orders.update_status',
    description=(
        'Transition an order to a new status along its lifecycle. Pass '
        '`order_number`, `status` (one of: confirmed, processing, fulfilled, '
        'shipped, delivered, cancelled), and `confirmed=True` after the user '
        'has approved. Refunds route through the refund flow, not here.'
    ),
    scopes=['orders.write'],
    schema={
        'type': 'object',
        'properties': {
            'order_number': {'type': 'string'},
            'status': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
        },
        'required': ['order_number', 'status'],
    },
    requires_approval=True,
    supports_staging=True,
)
def orders_update_status_tool(
    *, order_number: str, status: str, confirmed: bool = False, context: dict | None = None
) -> ToolResult:
    staged = _is_staged(context)
    if not staged:
        _require_confirmed(confirmed)
    from plugins.installed.orders.models import Order

    try:
        o = Order.objects.get(order_number=order_number)
    except Order.DoesNotExist:
        raise ToolError(f'order not found: {order_number}')  # noqa: B904
    prev = o.status
    if staged:
        return _stage(
            context=context,
            tool_name='orders.update_status',
            kind='order.update',
            title=f'Order #{order_number}: {prev} → {status}',
            summary=f'Set order #{order_number} status from {prev!r} to {status!r}.',
            changes=[{'object': _obj_ref(o), 'field': 'status', 'old': prev, 'new': status}],
            target=o,
        )
    # Order.status is a protected FSMField — direct assignment raises. Go through
    # the transition method, which validates the move and logs the OrderEvent /
    # runs side-effects a bare assign skips.
    transition_name = _ORDER_TRANSITIONS.get(status)
    if transition_name is None:
        raise ToolError(
            f'unsupported target status {status!r}; allowed: ' + ', '.join(_ORDER_TRANSITIONS)
        )
    try:
        from django_fsm import TransitionNotAllowed
    except Exception:  # noqa: BLE001 — degraded boot without django-fsm
        TransitionNotAllowed = Exception  # type: ignore[assignment,misc]
    try:
        getattr(o, transition_name)()
        o.save()
    except TransitionNotAllowed as e:
        raise ToolError(f'cannot move order #{order_number} from {prev} to {status}') from e
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'save failed: {e}') from e
    return ToolResult(
        output={'order_number': order_number, 'previous_status': prev, 'new_status': status},
        display=f'#{order_number}: {prev} → {status}',
    )


@tool(
    name='orders.cancel',
    description=(
        'Cancel an order. Sets status to `cancelled` and records the reason. '
        'Requires `confirmed=True`.'
    ),
    scopes=['orders.write'],
    schema={
        'type': 'object',
        'properties': {
            'order_number': {'type': 'string'},
            'reason': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
        },
        'required': ['order_number'],
    },
    requires_approval=True,
    supports_staging=True,
)
def orders_cancel_tool(
    *, order_number: str, reason: str = '', confirmed: bool = False, context: dict | None = None
) -> ToolResult:
    staged = _is_staged(context)
    if not staged:
        _require_confirmed(confirmed)
    from plugins.installed.orders.models import Order

    try:
        o = Order.objects.get(order_number=order_number)
    except Order.DoesNotExist:
        raise ToolError(f'order not found: {order_number}')  # noqa: B904
    if o.status in ('cancelled', 'refunded'):
        raise ToolError(f'already {o.status}')
    prev = o.status
    if staged:
        return _stage(
            context=context,
            tool_name='orders.cancel',
            kind='order.cancel',
            title=f'Cancel order #{order_number}',
            summary=reason.strip() or f'Cancel order #{order_number} (status {prev!r}).',
            changes=[{'object': _obj_ref(o), 'field': 'status', 'old': prev, 'new': 'cancelled'}],
            target=o,
        )
    # FSM transition (source='*' → 'cancelled'): flips the protected status
    # field, sets cancelled_at, and logs the OrderEvent.
    try:
        from django_fsm import TransitionNotAllowed
    except Exception:  # noqa: BLE001 — degraded boot without django-fsm
        TransitionNotAllowed = Exception  # type: ignore[assignment,misc]
    try:
        o.cancel(reason=f'Assistant: {reason}' if reason else 'Cancelled by Assistant')
        o.save()
    except TransitionNotAllowed as e:
        raise ToolError(f'cannot cancel order #{order_number} (status {prev})') from e
    except Exception as e:  # noqa: BLE001
        raise ToolError(f'cancel failed: {e}') from e
    return ToolResult(
        output={
            'order_number': order_number,
            'previous_status': prev,
            'new_status': 'cancelled',
            'reason': reason,
        },
        display=f'#{order_number} cancelled',
    )


@tool(
    name='orders.add_note',
    description=(
        'Append a note to an order (visible to staff, not the customer). Requires `confirmed=True`.'
    ),
    scopes=['orders.write'],
    schema={
        'type': 'object',
        'properties': {
            'order_number': {'type': 'string'},
            'note': {'type': 'string'},
            'confirmed': {'type': 'boolean', 'default': False},
        },
        'required': ['order_number', 'note'],
    },
    requires_approval=True,
    supports_staging=True,
)
def orders_add_note_tool(
    *, order_number: str, note: str, confirmed: bool = False, context: dict | None = None
) -> ToolResult:
    staged = _is_staged(context)
    if not staged:
        _require_confirmed(confirmed)
    from plugins.installed.orders.models import Order

    if not note.strip():
        raise ToolError('note cannot be empty')
    try:
        o = Order.objects.get(order_number=order_number)
    except Order.DoesNotExist:
        raise ToolError(f'order not found: {order_number}')  # noqa: B904
    old_raw = getattr(o, 'notes', '') or ''
    existing = old_raw.strip()
    sep = '\n\n' if existing else ''
    if staged:
        if not hasattr(o, 'notes'):
            # Without the field the change could never apply — refuse at staging
            # time (the unstaged path fails at save() the same way).
            raise ToolError('order model has no `notes` field — cannot stage a note')
        return _stage(
            context=context,
            tool_name='orders.add_note',
            kind='order.note',
            title=f'Add note to order #{order_number}',
            summary=f'Append a staff note to order #{order_number}.',
            changes=[
                {
                    'object': _obj_ref(o),
                    'field': 'notes',
                    'old': old_raw,
                    'new': f'{existing}{sep}{note.strip()}',
                }
            ],
            target=o,
        )
    o.notes = f'{existing}{sep}{note.strip()}'
    o.save(update_fields=['notes', 'updated_at'])
    return ToolResult(
        output={'order_number': order_number, 'appended': True},
        display=f'note added to #{order_number}',
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


# ── Analytics (order-derived) ───────────────────────────────────────────────
# analytics.summary / analytics.top_products were migrated here from
# core/assistant/tools/ecommerce.py: they aggregate the Order / OrderItem models,
# so the orders plugin is their correct home. Tool names unchanged.


@tool(
    name='analytics.summary',
    description=(
        'Sales summary for the last `days_back` days: revenue, orders, '
        'AOV, new customers. Default 7 days. Use this before drilling '
        'into specifics — gives the LLM the right framing.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'days_back': {'type': 'integer', 'minimum': 1, 'maximum': 365, 'default': 7},
        },
    },
)
def analytics_summary_tool(*, days_back: int = 7) -> ToolResult:
    from django.contrib.auth import get_user_model
    from django.db.models import Sum
    from django.utils import timezone

    from plugins.installed.orders.models import Order

    days = max(1, min(int(days_back or 7), 365))
    since = timezone.now() - timedelta(days=days)
    prev_since = since - timedelta(days=days)
    cur = Order.objects.filter(placed_at__gte=since)
    prev = Order.objects.filter(placed_at__gte=prev_since, placed_at__lt=since)
    cur_count = cur.count()
    cur_rev = cur.aggregate(t=Sum('total'))['t'] or Decimal('0')
    prev_count = prev.count()
    prev_rev = prev.aggregate(t=Sum('total'))['t'] or Decimal('0')
    aov = (cur_rev / cur_count) if cur_count else Decimal('0')
    User = get_user_model()
    new_customers = User.objects.filter(date_joined__gte=since).count()

    def pct(now, before):
        if not before:
            return None
        return float(
            ((Decimal(now) - Decimal(before)) / Decimal(before) * Decimal('100')).quantize(
                Decimal('0.01')
            )
        )

    return ToolResult(
        output={
            'window_days': days,
            'orders': cur_count,
            'orders_prev': prev_count,
            'orders_pct_change': pct(cur_count, prev_count),
            'revenue': str(cur_rev),
            'revenue_prev': str(prev_rev),
            'revenue_pct_change': pct(cur_rev, prev_rev),
            'avg_order_value': str(aov),
            'new_customers': new_customers,
        }
    )


@tool(
    name='analytics.top_products',
    description=(
        'Top-N products by revenue or units sold over the last `days_back` '
        'days. Default 30 days, sort by revenue.'
    ),
    scopes=['system.read'],
    schema={
        'type': 'object',
        'properties': {
            'days_back': {'type': 'integer', 'minimum': 1, 'maximum': 365, 'default': 30},
            'by': {'type': 'string', 'enum': ['revenue', 'units'], 'default': 'revenue'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 10},
        },
    },
)
def analytics_top_products_tool(
    *, days_back: int = 30, by: str = 'revenue', limit: int = 10
) -> ToolResult:
    from django.db.models import Sum
    from django.utils import timezone

    from plugins.installed.orders.models import OrderItem

    days = max(1, min(int(days_back or 30), 365))
    since = timezone.now() - timedelta(days=days)
    qs = (
        OrderItem.objects.filter(order__placed_at__gte=since)
        .values('product_id', 'product_name')
        .annotate(units=Sum('quantity'), revenue=Sum('total_price'))
    )
    sort_key = '-revenue' if by != 'units' else '-units'
    qs = qs.order_by(sort_key)[: max(1, min(int(limit or 10), 50))]
    rows = [
        {
            'product_id': str(r['product_id']) if r['product_id'] else '',
            'name': r['product_name'] or '',
            'units': int(r['units'] or 0),
            'revenue': str(r['revenue'] or 0),
        }
        for r in qs
    ]
    return ToolResult(
        output={'window_days': days, 'sort': by, 'products': rows},
        display=f'top {len(rows)} by {by}',
    )

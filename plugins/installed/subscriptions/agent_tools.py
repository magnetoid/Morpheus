"""Agent commands for subscriptions — lets Linda list a customer's
subscriptions and pause / resume / cancel them. Contributed via
`SubscriptionsPlugin.contribute_agent_tools` (present only while enabled).
"""

from __future__ import annotations

from core.agents import tool
from core.agents.tools import ToolResult


def _plan_name(sub) -> str:
    plan = getattr(sub, 'plan', None)
    return getattr(plan, 'name', '') or str(plan or '')


def _brief(sub) -> dict:
    return {
        'id': str(sub.id),
        'customer': getattr(sub.customer, 'email', '') or str(sub.customer_id),
        'plan': _plan_name(sub),
        'state': sub.state,
        'cancel_at_period_end': sub.cancel_at_period_end,
        'current_period_end': sub.current_period_end.isoformat()
        if sub.current_period_end
        else None,
    }


@tool(
    name='subscriptions.list',
    description=(
        'List subscriptions, newest first. Filter by customer email and/or state '
        '(trialing/active/past_due/paused/cancelled/expired).'
    ),
    scopes=['orders.read'],
    schema={
        'type': 'object',
        'properties': {
            'email': {'type': 'string', 'description': 'Filter by customer email.'},
            'state': {'type': 'string', 'description': 'Filter by subscription state.'},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20},
        },
    },
)
def subscriptions_list_tool(*, email: str = '', state: str = '', limit: int = 20) -> ToolResult:
    from plugins.installed.subscriptions.models import Subscription

    qs = Subscription.objects.select_related('customer', 'plan').all()
    if email.strip():
        qs = qs.filter(customer__email__iexact=email.strip())
    if state.strip():
        qs = qs.filter(state=state.strip())
    try:
        n = max(1, min(int(limit or 20), 50))
    except (TypeError, ValueError):
        n = 20
    rows = [_brief(s) for s in qs[:n]]
    return ToolResult(
        output={'subscriptions': rows, 'count': len(rows)}, display=f'{len(rows)} subscription(s).'
    )


def _get(subscription_id: str):
    from plugins.installed.subscriptions.models import Subscription

    return (
        Subscription.objects.select_related('customer', 'plan').filter(id=subscription_id).first()
    )


@tool(
    name='subscriptions.pause',
    description='Pause an active or trialing subscription. Reversible with subscriptions.resume.',
    scopes=['orders.write'],
    schema={
        'type': 'object',
        'properties': {'subscription_id': {'type': 'string'}},
        'required': ['subscription_id'],
    },
)
def subscriptions_pause_tool(*, subscription_id: str) -> ToolResult:
    sub = _get(subscription_id)
    if sub is None:
        return ToolResult(output={'error': f'no subscription {subscription_id!r}'})
    if sub.state not in ('active', 'trialing'):
        return ToolResult(output={'error': f'cannot pause from state {sub.state!r}'})
    sub.state = 'paused'
    sub.save(update_fields=['state'])
    return ToolResult(output=_brief(sub), display=f'Paused {_plan_name(sub)}.')


@tool(
    name='subscriptions.resume',
    description='Resume a paused subscription back to active.',
    scopes=['orders.write'],
    schema={
        'type': 'object',
        'properties': {'subscription_id': {'type': 'string'}},
        'required': ['subscription_id'],
    },
)
def subscriptions_resume_tool(*, subscription_id: str) -> ToolResult:
    sub = _get(subscription_id)
    if sub is None:
        return ToolResult(output={'error': f'no subscription {subscription_id!r}'})
    if sub.state != 'paused':
        return ToolResult(output={'error': f'cannot resume from state {sub.state!r}'})
    sub.state = 'active'
    sub.save(update_fields=['state'])
    return ToolResult(output=_brief(sub), display=f'Resumed {_plan_name(sub)}.')


@tool(
    name='subscriptions.cancel',
    description=(
        'Cancel a subscription. By default cancels at the end of the current '
        'period (the customer keeps access until then); pass at_period_end=false '
        'to cancel immediately. Confirm with the user first — this affects billing.'
    ),
    scopes=['orders.cancel'],
    schema={
        'type': 'object',
        'properties': {
            'subscription_id': {'type': 'string'},
            'at_period_end': {'type': 'boolean', 'default': True},
        },
        'required': ['subscription_id'],
    },
)
def subscriptions_cancel_tool(*, subscription_id: str, at_period_end: bool = True) -> ToolResult:
    from django.utils import timezone

    sub = _get(subscription_id)
    if sub is None:
        return ToolResult(output={'error': f'no subscription {subscription_id!r}'})
    if sub.state in ('cancelled', 'expired'):
        return ToolResult(output={'error': f'already {sub.state}'})
    if at_period_end:
        sub.cancel_at_period_end = True
        sub.save(update_fields=['cancel_at_period_end'])
        msg = 'Will cancel at period end.'
    else:
        sub.state = 'cancelled'
        sub.cancelled_at = timezone.now()
        sub.cancel_at_period_end = False
        sub.save(update_fields=['state', 'cancelled_at', 'cancel_at_period_end'])
        msg = 'Cancelled immediately.'
    return ToolResult(output=_brief(sub), display=msg)

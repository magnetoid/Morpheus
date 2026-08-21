"""Analytics tools — aggregate read access for the Merchant Ops agent."""

from __future__ import annotations

from datetime import timedelta

from morpheus.core import ToolResult, tool


@tool(
    name='analytics.revenue_summary',
    description='Total revenue and order count for the last `days` days.',
    scopes=['analytics.read'],
    schema={
        'type': 'object',
        'properties': {
            'days': {'type': 'integer', 'minimum': 1, 'maximum': 365, 'default': 30},
        },
    },
)
def revenue_summary_tool(*, days: int = 30) -> ToolResult:
    from django.db.models import Count, Sum
    from django.utils import timezone

    from plugins.installed.orders.models import Order

    days = max(1, min(int(days or 30), 365))
    since = timezone.now() - timedelta(days=days)
    qs = Order.objects.filter(
        created_at__gte=since, state__in=['paid', 'shipped', 'delivered', 'completed']
    )
    agg = qs.aggregate(total=Sum('total'), n=Count('id'))
    return ToolResult(
        output={
            'days': days,
            'order_count': agg['n'] or 0,
            'revenue': str(agg['total'].amount) if agg.get('total') is not None else '0',
            'currency': str(agg['total'].currency) if agg.get('total') is not None else '',
        }
    )


# NB `analytics.top_products` used to have a weaker twin here (units-only,
# subset of orders'). Deleted v0.55.0: the orders plugin owns that name —
# it aggregates Order/OrderItem, and last-writer-wins registration made the
# served implementation depend on plugin load order.

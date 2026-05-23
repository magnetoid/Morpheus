"""Analytics tools — aggregate read access for the Merchant Ops agent."""
from __future__ import annotations

from datetime import timedelta

from core.agents import ToolResult, tool


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
    qs = Order.objects.filter(created_at__gte=since, state__in=['paid', 'shipped', 'delivered', 'completed'])
    agg = qs.aggregate(total=Sum('total'), n=Count('id'))
    return ToolResult(output={
        'days': days,
        'order_count': agg['n'] or 0,
        'revenue': str(agg['total'].amount) if agg.get('total') is not None else '0',
        'currency': str(agg['total'].currency) if agg.get('total') is not None else '',
    })


@tool(
    name='analytics.top_products',
    description='Best-selling products in the last `days` days.',
    scopes=['analytics.read'],
    schema={
        'type': 'object',
        'properties': {
            'days': {'type': 'integer', 'minimum': 1, 'maximum': 365, 'default': 30},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 25, 'default': 10},
        },
    },
)
def top_products_tool(*, days: int = 30, limit: int = 10) -> ToolResult:
    from django.db.models import Sum
    from django.utils import timezone

    from plugins.installed.orders.models import OrderItem

    days = max(1, min(int(days or 30), 365))
    limit = max(1, min(int(limit or 10), 25))
    since = timezone.now() - timedelta(days=days)
    # Order's timestamp field is `placed_at`, not `created_at`. The previous
    # filter raised FieldError on every call — fixed 2026-05-23.
    rows = (
        OrderItem.objects
        .filter(order__placed_at__gte=since, product__isnull=False)
        .values('product__name', 'product__slug')
        .annotate(units=Sum('quantity'))
        .order_by('-units')[:limit]
    )
    return ToolResult(output={
        'days': days,
        'products': [
            {'name': r['product__name'], 'slug': r['product__slug'], 'units': r['units']}
            for r in rows
        ],
    })

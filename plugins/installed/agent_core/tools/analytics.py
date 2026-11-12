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
    from django.utils import timezone

    from plugins.installed.orders.models import Order
    from plugins.installed.orders.reports import net_sales

    days = max(1, min(int(days or 30), 365))
    since = timezone.now() - timedelta(days=days)
    # The one sales rule (orders.reports): orders placed and not cancelled,
    # after their refunds. payment_status='paid' left out cash on delivery,
    # bank transfers and held cards.
    sales = net_sales(Order.objects.filter(placed_at__gte=since))
    currencies = sorted({sales.currency, *sales.others} - {''})
    if len(currencies) == 1:
        currency = currencies[0]
    else:
        currency = f'mixed ({", ".join(currencies)})' if currencies else ''
    return ToolResult(
        output={
            'days': days,
            'order_count': sales.orders,
            'revenue': str(sales.net),
            'currency': currency,
        }
    )


# NB `analytics.top_products` used to have a weaker twin here (units-only,
# subset of orders'). Deleted v0.55.0: the orders plugin owns that name —
# it aggregates Order/OrderItem, and last-writer-wins registration made the
# served implementation depend on plugin load order.

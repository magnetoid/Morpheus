"""Analytics agent tools — replaces the older stubs in agent_core/tools/analytics.py.

These are richer, multi-dimensional. The old `analytics.revenue_summary` and
`analytics.top_products` agent tools query the live `Order` table — keep them.
The new ones below query the analytics rollups so they're cheap and cover
funnels / sources / agent activity that orders can't see.
"""

from __future__ import annotations

from core.agents import ToolResult, tool


@tool(
    name='analytics.summary',
    description='Headline numbers for the last N days (sessions, pageviews, orders, revenue, conversion funnel).',
    scopes=['analytics.read'],
    schema={
        'type': 'object',
        'properties': {
            'days': {'type': 'integer', 'minimum': 1, 'maximum': 365, 'default': 7},
        },
    },
)
def analytics_summary_tool(*, days: int = 7) -> ToolResult:
    from plugins.installed.analytics.services import summary_for

    s = summary_for(days=int(days or 7))
    if s.get('revenue') is not None:
        s['revenue'] = {'amount': str(s['revenue'].amount), 'currency': str(s['revenue'].currency)}
    return ToolResult(
        output=s,
        display=f'{s["sessions"]} sessions, {s["orders"]} orders, last {s["window_days"]}d',
    )


@tool(
    name='analytics.funnel',
    description='Conversion funnel — distinct sessions hitting each step in order.',
    scopes=['analytics.read'],
    schema={
        'type': 'object',
        'properties': {
            'steps': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Ordered list of event names (default: pageview → product.viewed → cart.add → order.placed)',
            },
            'days': {'type': 'integer', 'minimum': 1, 'maximum': 365, 'default': 30},
        },
    },
)
def analytics_funnel_tool(*, steps: list[str] | None = None, days: int = 30) -> ToolResult:
    from plugins.installed.analytics.services import funnel_for

    steps = steps or ['pageview', 'product.viewed', 'cart.add', 'order.placed']
    rows = funnel_for(steps=steps, days=int(days or 30))
    base = rows[0]['sessions'] if rows else 0
    for r in rows:
        r['conversion_pct'] = round((100.0 * r['sessions'] / base), 1) if base else 0.0
    return ToolResult(output={'days': days, 'funnel': rows})


@tool(
    name='analytics.search_trends',
    description='Top search queries in the analytics rollups for the last N days.',
    scopes=['analytics.read'],
    schema={
        'type': 'object',
        'properties': {
            'days': {'type': 'integer', 'minimum': 1, 'maximum': 365, 'default': 30},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20},
        },
    },
)
def analytics_search_trends_tool(*, days: int = 30, limit: int = 20) -> ToolResult:
    from plugins.installed.analytics.services import top_searches

    return ToolResult(
        output={
            'days': days,
            'searches': top_searches(days=int(days or 30), limit=int(limit or 20)),
        }
    )


@tool(
    name='analytics.realtime',
    description='What is happening on the storefront right now (last N minutes).',
    scopes=['analytics.read'],
    schema={
        'type': 'object',
        'properties': {
            'minutes': {'type': 'integer', 'minimum': 1, 'maximum': 1440, 'default': 30},
        },
    },
)
def analytics_realtime_tool(*, minutes: int = 30) -> ToolResult:
    from plugins.installed.analytics.services import real_time

    data = real_time(minutes=int(minutes or 30))
    for r in data['recent']:
        r['created_at'] = (
            r['created_at'].isoformat()
            if hasattr(r['created_at'], 'isoformat')
            else r['created_at']
        )
    return ToolResult(
        output=data,
        display=f'{data["sessions"]} sessions, {data["events"]} events in last {minutes} min',
    )


@tool(
    name='analytics.agent_costs',
    description='Agent activity stats: which agents ran how often (last N days).',
    scopes=['analytics.read'],
    schema={
        'type': 'object',
        'properties': {
            'days': {'type': 'integer', 'minimum': 1, 'maximum': 365, 'default': 30},
        },
    },
)
def analytics_agent_costs_tool(*, days: int = 30) -> ToolResult:
    from plugins.installed.analytics.services import agent_activity

    return ToolResult(output={'days': days, 'agents': agent_activity(days=int(days or 30))})


@tool(
    name='analytics.top_products',
    description='Top viewed products from the analytics rollups (last N days).',
    scopes=['analytics.read'],
    schema={
        'type': 'object',
        'properties': {
            'days': {'type': 'integer', 'minimum': 1, 'maximum': 365, 'default': 30},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 10},
        },
    },
)
def analytics_top_products_tool(*, days: int = 30, limit: int = 10) -> ToolResult:
    from plugins.installed.analytics.services import top_products

    return ToolResult(
        output={
            'days': days,
            'products': top_products(days=int(days or 30), limit=int(limit or 10)),
        }
    )

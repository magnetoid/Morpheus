"""Analytics agent tools — the ROLLUP view (sessions, funnels, sources).

The Order-table view lives in the orders plugin (`analytics.summary` /
`analytics.top_products` aggregate Order/OrderItem there — orders owns those
names). The tools below query the analytics rollups, so they're cheap and
cover traffic/funnels/agent activity that orders can't see; their names say
so (`traffic_summary`, `top_viewed_products`) after v0.55.0 retired the
load-order-dependent name collisions.
"""

from __future__ import annotations

from morpheus.core import ToolResult, tool


@tool(
    name='analytics.traffic_summary',
    description=(
        'Headline numbers for today and the N-1 days before it on the store clock: visits '
        "(the 'sessions' key; a visit ends after 30 quiet minutes), visitors, pageviews, "
        'orders, revenue and the funnel counts.'
    ),
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
        display=f'{s["sessions"]} visits, {s.get("visitors", 0)} visitors, {s["orders"]} orders, last {s["window_days"]}d',
    )


@tool(
    name='analytics.funnel',
    description=(
        'Conversion funnel: distinct visits reaching each step in order. Give `preset` '
        "(a funnel the store's apps offer, e.g. 'shop' or 'bookings'; the answer lists them) "
        'or your own `steps` (event names). Without either, the funnel the Funnel page '
        'opens on.'
    ),
    scopes=['analytics.read'],
    schema={
        'type': 'object',
        'properties': {
            'preset': {
                'type': 'string',
                'description': "A preset's key, e.g. 'shop' or 'bookings'",
            },
            'steps': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': 'Ordered list of event names; overrides the preset',
            },
            'days': {'type': 'integer', 'minimum': 1, 'maximum': 365, 'default': 30},
        },
    },
)
def analytics_funnel_tool(
    *, preset: str = '', steps: list[str] | None = None, days: int = 30
) -> ToolResult:
    from plugins.installed.analytics.services import default_funnel, funnel_for, funnel_presets

    presets = funnel_presets()
    chosen = None
    if not steps:
        chosen = next((p for p in presets if p['key'] == preset), None) or default_funnel(presets)
        steps = chosen['steps']
    rows = funnel_for(steps=steps, days=int(days or 30))
    base = rows[0]['sessions'] if rows else 0
    for r in rows:
        r['conversion_pct'] = round((100.0 * r['sessions'] / base), 1) if base else 0.0
    return ToolResult(
        output={
            'days': days,
            'preset': chosen['key'] if chosen else None,
            'presets': [{'key': p['key'], 'label': p['label']} for p in presets],
            'funnel': rows,
        }
    )


@tool(
    name='analytics.search_trends',
    description=(
        'Search terms shoppers typed in the store over today and the N-1 days before it: '
        "the most searched ('top'), those that found no products ('no_results', with the "
        'filters such searches were made with: region, date, category, guests), or those '
        "searched in visits that then placed an order ('led_to_sale')."
    ),
    scopes=['analytics.read'],
    schema={
        'type': 'object',
        'properties': {
            'days': {'type': 'integer', 'minimum': 1, 'maximum': 365, 'default': 30},
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20},
            'kind': {
                'type': 'string',
                'enum': ['top', 'no_results', 'led_to_sale'],
                'default': 'top',
            },
        },
    },
)
def analytics_search_trends_tool(
    *, days: int = 30, limit: int = 20, kind: str = 'top'
) -> ToolResult:
    from plugins.installed.analytics.services import no_results_by_filter
    from plugins.installed.analytics.visits import SEARCH_REPORTS, search_terms

    kind = kind if kind in SEARCH_REPORTS else 'top'
    days, limit = int(days or 30), int(limit or 20)
    output = {
        'days': days,
        'kind': kind,
        'searches': search_terms(days=days, kind=kind, limit=limit),
    }
    if kind == 'no_results':
        output['filters'] = [
            {**row, 'last_seen': row['last_seen'].isoformat()}
            for row in no_results_by_filter(days=days, limit=limit)
        ]
    return ToolResult(output=output)


@tool(
    name='analytics.traffic_sources',
    description=(
        'Where visits came from over today and the N-1 days before it on the store clock: '
        'visits, visitors, orders, conversion (visits with an order over visits) and net sales, '
        'grouped by channel (organic search, paid ads, social, email, AI assistants, other '
        'sites, direct), source, campaign, landing page, country or device, with each '
        "group's visits in the period before. Each visit is filed under its own first page."
    ),
    scopes=['analytics.read'],
    schema={
        'type': 'object',
        'properties': {
            'days': {'type': 'integer', 'minimum': 1, 'maximum': 365, 'default': 30},
            'by': {
                'type': 'string',
                'enum': ['channel', 'source', 'campaign', 'landing', 'country', 'device'],
                'default': 'channel',
            },
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'default': 20},
        },
    },
)
def analytics_traffic_sources_tool(
    *, days: int = 30, by: str = 'channel', limit: int = 20
) -> ToolResult:
    from plugins.installed.analytics.visits import sources_report

    report = sources_report(days=int(days or 30), by=by, limit=int(limit or 20))

    def _money(value):
        return (
            None
            if value is None
            else {'amount': str(value.amount), 'currency': str(value.currency)}
        )

    for row in report['rows']:
        row['sales'] = _money(row['sales'])
    report['totals']['sales'] = _money(report['totals']['sales'])
    top = report['rows'][0]['label'] if report['rows'] else 'none'
    return ToolResult(
        output=report,
        display=f'{report["totals"]["visits"]} visits in {report["days"]}d; most from {top}',
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
    name='analytics.top_viewed_products',
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


@tool(
    name='analytics.ai_traffic',
    description=(
        'AI-visibility picture for the last N days: human sessions + revenue '
        'arriving FROM AI assistants (ChatGPT/Perplexity/Claude/Gemini '
        'referrals), and AI-crawler reads of the catalog (GPTBot, ClaudeBot, '
        'PerplexityBot, ...). Use for "is AI sending me customers?" questions '
        'and the daily briefing.'
    ),
    scopes=['analytics.read'],
    schema={
        'type': 'object',
        'properties': {
            'days': {'type': 'integer', 'minimum': 1, 'maximum': 365, 'default': 30},
        },
    },
)
def analytics_ai_traffic_tool(*, days: int = 30) -> ToolResult:
    from plugins.installed.analytics.services import ai_traffic_summary

    s = ai_traffic_summary(days=int(days or 30))
    sessions = sum(s['assistant_sessions'].values())
    return ToolResult(
        output=s,
        display=(
            f'{sessions} AI-referred sessions, {s["assistant_revenue_total"]} revenue, '
            f'{s["crawler_hits_total"]} crawler reads, last {s["days"]}d'
        ),
    )

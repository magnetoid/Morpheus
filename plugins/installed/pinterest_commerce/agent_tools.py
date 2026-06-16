"""Pinterest Commerce agent tools — feed audit + Ads reporting for Linda."""

from __future__ import annotations

from core.agents import ToolResult, tool


@tool(
    name='pinterest.feed_coverage',
    description='Audit Pinterest catalog feed eligibility: how many active products are catalog-eligible and what attributes are missing.',
    scopes=['catalog.read'],
    schema={
        'type': 'object',
        'properties': {'limit': {'type': 'integer', 'minimum': 1, 'maximum': 5000}},
    },
)
def pinterest_feed_coverage_tool(*, limit: int | None = None) -> ToolResult:
    from plugins.installed.pinterest_commerce.services.coverage import coverage_report

    rep = coverage_report(limit=limit)
    return ToolResult(
        output=rep, display=f'{rep["eligible"]}/{rep["total"]} eligible ({rep["eligible_pct"]}%)'
    )


@tool(
    name='pinterest.feed_url',
    description='Return the public Pinterest catalog feed URL to add as a data source in Pinterest Catalogs.',
    scopes=['catalog.read'],
    schema={'type': 'object', 'properties': {}},
)
def pinterest_feed_url_tool() -> ToolResult:
    from core.utils.site import site_base_url

    url = site_base_url().rstrip('/') + '/feeds/pinterest-catalog.xml'
    return ToolResult(output={'url': url}, display=url)


@tool(
    name='pinterest.feed_diagnostics',
    description='Live Pinterest catalog feed processing status: product counts + top item-level errors (why feed items fail). Requires Pinterest connected with a catalog feed ID.',
    scopes=['catalog.read'],
    schema={'type': 'object', 'properties': {}},
)
def pinterest_feed_diagnostics_tool() -> ToolResult:
    from plugins.installed.pinterest_commerce.services.diagnostics import feed_diagnostics

    d = feed_diagnostics()
    if not d.get('ok'):
        return ToolResult(output=d, display=f'Not connected ({d.get("reason")})')
    return ToolResult(
        output=d, display=f'{len(d["issues"])} issue types · counts {d.get("counts")}'
    )


@tool(
    name='pinterest.ads_report',
    description='Pinterest Ads campaign performance for the last N days (spend, clicks, checkouts). Requires Pinterest Ads connected.',
    scopes=['analytics.read'],
    schema={
        'type': 'object',
        'properties': {'days': {'type': 'integer', 'enum': [7, 14, 30], 'default': 30}},
    },
)
def pinterest_ads_report_tool(*, days: int = 30) -> ToolResult:
    from plugins.installed.pinterest_commerce.services.ads_api import campaign_report

    rep = campaign_report(days=days)
    if not rep.get('ok'):
        return ToolResult(output=rep, display=f'Pinterest Ads not connected ({rep.get("reason")})')
    t = rep['totals']
    return ToolResult(output=rep, display=f'{len(rep["campaigns"])} campaigns · spend {t["spend"]}')

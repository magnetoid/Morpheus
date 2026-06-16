"""TikTok Commerce agent tools — feed audit + Ads reporting for Linda."""

from __future__ import annotations

from core.agents import ToolResult, tool


@tool(
    name='tiktok.feed_coverage',
    description='Audit TikTok catalog feed eligibility: how many active products are catalog-eligible and what attributes are missing.',
    scopes=['catalog.read'],
    schema={
        'type': 'object',
        'properties': {'limit': {'type': 'integer', 'minimum': 1, 'maximum': 5000}},
    },
)
def tiktok_feed_coverage_tool(*, limit: int | None = None) -> ToolResult:
    from plugins.installed.tiktok_commerce.services.coverage import coverage_report

    rep = coverage_report(limit=limit)
    return ToolResult(
        output=rep, display=f'{rep["eligible"]}/{rep["total"]} eligible ({rep["eligible_pct"]}%)'
    )


@tool(
    name='tiktok.feed_url',
    description='Return the public TikTok catalog feed URL to add as a data feed in TikTok Catalog Manager.',
    scopes=['catalog.read'],
    schema={'type': 'object', 'properties': {}},
)
def tiktok_feed_url_tool() -> ToolResult:
    from core.utils.site import site_base_url

    url = site_base_url().rstrip('/') + '/feeds/tiktok-catalog.xml'
    return ToolResult(output={'url': url}, display=url)


@tool(
    name='tiktok.catalog_diagnostics',
    description='Live TikTok catalog review status: approved/pending/rejected counts + top reject reasons. Requires TikTok connected with a catalog ID.',
    scopes=['catalog.read'],
    schema={'type': 'object', 'properties': {}},
)
def tiktok_catalog_diagnostics_tool() -> ToolResult:
    from plugins.installed.tiktok_commerce.services.diagnostics import catalog_diagnostics

    d = catalog_diagnostics()
    if not d.get('ok'):
        return ToolResult(output=d, display=f'Not connected ({d.get("reason")})')
    c = d['counts']
    return ToolResult(
        output=d,
        display=f'{c["approved"]} approved · {c["rejected"]} rejected · {len(d["issues"])} issue types',
    )


@tool(
    name='tiktok.ads_report',
    description='TikTok Ads campaign performance for the last N days (spend, clicks, conversions). Requires TikTok Ads connected.',
    scopes=['analytics.read'],
    schema={
        'type': 'object',
        'properties': {'days': {'type': 'integer', 'enum': [7, 14, 30], 'default': 30}},
    },
)
def tiktok_ads_report_tool(*, days: int = 30) -> ToolResult:
    from plugins.installed.tiktok_commerce.services.ads_api import campaign_report

    rep = campaign_report(days=days)
    if not rep.get('ok'):
        return ToolResult(output=rep, display=f'TikTok Ads not connected ({rep.get("reason")})')
    t = rep['totals']
    return ToolResult(output=rep, display=f'{len(rep["campaigns"])} campaigns · spend {t["spend"]}')

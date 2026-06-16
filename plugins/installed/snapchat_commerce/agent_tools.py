"""Snapchat Commerce agent tools — feed audit + Ads reporting for Linda."""

from __future__ import annotations

from core.agents import ToolResult, tool


@tool(
    name='snapchat.feed_coverage',
    description='Audit Snapchat catalog feed eligibility: how many active products are catalog-eligible and what attributes are missing.',
    scopes=['catalog.read'],
    schema={
        'type': 'object',
        'properties': {'limit': {'type': 'integer', 'minimum': 1, 'maximum': 5000}},
    },
)
def snapchat_feed_coverage_tool(*, limit: int | None = None) -> ToolResult:
    from plugins.installed.snapchat_commerce.services.coverage import coverage_report

    rep = coverage_report(limit=limit)
    return ToolResult(
        output=rep, display=f'{rep["eligible"]}/{rep["total"]} eligible ({rep["eligible_pct"]}%)'
    )


@tool(
    name='snapchat.feed_url',
    description='Return the public Snapchat catalog feed URL to add as a product feed in Snapchat Catalog Manager (for Dynamic Ads).',
    scopes=['catalog.read'],
    schema={'type': 'object', 'properties': {}},
)
def snapchat_feed_url_tool() -> ToolResult:
    from core.utils.site import site_base_url

    url = site_base_url().rstrip('/') + '/feeds/snapchat-catalog.xml'
    return ToolResult(output={'url': url}, display=url)


@tool(
    name='snapchat.ads_report',
    description='Snapchat Ads campaign performance for the last N days (spend, swipes, conversions). Requires Snapchat Ads connected.',
    scopes=['analytics.read'],
    schema={
        'type': 'object',
        'properties': {'days': {'type': 'integer', 'enum': [7, 14, 30], 'default': 30}},
    },
)
def snapchat_ads_report_tool(*, days: int = 30) -> ToolResult:
    from plugins.installed.snapchat_commerce.services.ads_api import campaign_report

    rep = campaign_report(days=days)
    if not rep.get('ok'):
        return ToolResult(output=rep, display=f'Snapchat Ads not connected ({rep.get("reason")})')
    t = rep['totals']
    return ToolResult(output=rep, display=f'{len(rep["campaigns"])} campaigns · spend {t["spend"]}')

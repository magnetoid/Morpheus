"""Reddit Ads agent tools — campaigns + reporting for Linda."""

from __future__ import annotations

from core.agents import ToolResult, tool


@tool(
    name='reddit.campaigns',
    description='List Reddit Ads campaigns (id, name, status, objective). Requires Reddit Ads connected.',
    scopes=['analytics.read'],
    schema={'type': 'object', 'properties': {}},
)
def reddit_campaigns_tool() -> ToolResult:
    from plugins.installed.reddit_ads.services.ads_api import list_campaigns

    rep = list_campaigns()
    if not rep.get('ok'):
        return ToolResult(output=rep, display=f'Reddit Ads not connected ({rep.get("reason")})')
    return ToolResult(output=rep, display=f'{len(rep["campaigns"])} campaigns')


@tool(
    name='reddit.ads_report',
    description='Reddit Ads campaign performance for the last N days (spend, clicks, conversions). Requires Reddit Ads connected.',
    scopes=['analytics.read'],
    schema={
        'type': 'object',
        'properties': {'days': {'type': 'integer', 'enum': [7, 14, 30], 'default': 30}},
    },
)
def reddit_ads_report_tool(*, days: int = 30) -> ToolResult:
    from plugins.installed.reddit_ads.services.ads_api import campaign_report

    rep = campaign_report(days=days)
    if not rep.get('ok'):
        return ToolResult(output=rep, display=f'Reddit Ads not connected ({rep.get("reason")})')
    t = rep['totals']
    return ToolResult(
        output=rep, display=f'{len(rep["campaigns"])} campaigns · spend {t.get("spend")}'
    )

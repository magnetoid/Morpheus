"""Amazon Ads agent tools — campaigns + reporting for Linda."""

from __future__ import annotations

from core.agents import ToolResult, tool


@tool(
    name='amazon.campaigns',
    description='List Amazon Sponsored Products campaigns (id, name, state, daily budget). Requires Amazon Ads connected.',
    scopes=['analytics.read'],
    schema={'type': 'object', 'properties': {}},
)
def amazon_campaigns_tool() -> ToolResult:
    from plugins.installed.amazon_ads.services.ads_api import list_campaigns

    rep = list_campaigns()
    if not rep.get('ok'):
        return ToolResult(output=rep, display=f'Amazon Ads not connected ({rep.get("reason")})')
    return ToolResult(output=rep, display=f'{len(rep["campaigns"])} campaigns')


@tool(
    name='amazon.ads_report',
    description='Amazon Ads campaign performance (cost, clicks, purchases, sales) from the cached async report. Hit Refresh metrics on the dashboard first.',
    scopes=['analytics.read'],
    schema={'type': 'object', 'properties': {}},
)
def amazon_ads_report_tool() -> ToolResult:
    from plugins.installed.amazon_ads.services.reporting import cached_metrics

    m = cached_metrics()
    if not m or not m.get('metrics'):
        return ToolResult(
            output={'ok': False}, display='No cached metrics — refresh on the dashboard.'
        )
    rows = m['metrics']
    total_cost = round(sum(v.get('cost', 0) for v in rows.values()), 2)
    total_sales = round(sum(v.get('sales', 0) for v in rows.values()), 2)
    return ToolResult(
        output=m, display=f'{len(rows)} campaigns · cost {total_cost} · sales {total_sales}'
    )

"""Microsoft Commerce agent tools — feed audit for Linda."""

from __future__ import annotations

from morpheus.core import ToolResult, tool


@tool(
    name='microsoft.feed_coverage',
    description='Audit Microsoft Merchant Center feed eligibility: how many active products are catalog-eligible and what attributes are missing.',
    scopes=['catalog.read'],
    schema={
        'type': 'object',
        'properties': {'limit': {'type': 'integer', 'minimum': 1, 'maximum': 5000}},
    },
)
def microsoft_feed_coverage_tool(*, limit: int | None = None) -> ToolResult:
    from plugins.installed.microsoft_commerce.services.coverage import coverage_report

    rep = coverage_report(limit=limit)
    return ToolResult(
        output=rep, display=f'{rep["eligible"]}/{rep["total"]} eligible ({rep["eligible_pct"]}%)'
    )


@tool(
    name='microsoft.campaigns',
    description='List Microsoft Advertising campaigns (id, name, status, daily budget) for control. Requires Microsoft Ads connected. (No performance metrics — Microsoft reporting is async-SOAP, not built.)',
    scopes=['analytics.read'],
    schema={'type': 'object', 'properties': {}},
)
def microsoft_campaigns_tool() -> ToolResult:
    from plugins.installed.microsoft_commerce.services.ads_api import list_campaigns

    rep = list_campaigns()
    if not rep.get('ok'):
        return ToolResult(output=rep, display=f'Microsoft Ads not connected ({rep.get("reason")})')
    return ToolResult(output=rep, display=f'{len(rep["campaigns"])} campaigns')


@tool(
    name='microsoft.feed_url',
    description='Return the public Microsoft Merchant Center catalog feed URL to add as a feed in Microsoft Merchant Center.',
    scopes=['catalog.read'],
    schema={'type': 'object', 'properties': {}},
)
def microsoft_feed_url_tool() -> ToolResult:
    from morpheus.core import site_base_url

    url = site_base_url().rstrip('/') + '/feeds/microsoft-catalog.xml'
    return ToolResult(output={'url': url}, display=url)

"""Meta Commerce agent tools — feed audit + Ads reporting for Linda."""

from __future__ import annotations

from core.agents import ToolResult, tool


@tool(
    name='meta.feed_coverage',
    description='Audit Meta catalog feed eligibility: how many active products are catalog-eligible and what attributes are missing (image, price, gtin/mpn, brand).',
    scopes=['catalog.read'],
    schema={
        'type': 'object',
        'properties': {'limit': {'type': 'integer', 'minimum': 1, 'maximum': 5000}},
    },
)
def meta_feed_coverage_tool(*, limit: int | None = None) -> ToolResult:
    from plugins.installed.meta_commerce.services.coverage import coverage_report

    rep = coverage_report(limit=limit)
    return ToolResult(
        output=rep, display=f'{rep["eligible"]}/{rep["total"]} eligible ({rep["eligible_pct"]}%)'
    )


@tool(
    name='meta.feed_url',
    description='Return the public Meta catalog feed URL to add as a data source in Commerce Manager.',
    scopes=['catalog.read'],
    schema={'type': 'object', 'properties': {}},
)
def meta_feed_url_tool() -> ToolResult:
    from core.utils.site import site_base_url

    url = site_base_url().rstrip('/') + '/feeds/meta-catalog.xml'
    return ToolResult(output={'url': url}, display=url)


@tool(
    name='meta.rebuild_feed',
    description='Rebuild the Meta catalog feed now; report items written and skipped.',
    scopes=['catalog.write'],
    schema={'type': 'object', 'properties': {}},
)
def meta_rebuild_feed_tool() -> ToolResult:
    from django.core.cache import cache

    from plugins.installed.meta_commerce.services.feed import build_feed
    from plugins.installed.meta_commerce.views import FEED_CACHE_KEY

    xml, stats = build_feed()
    cache.set(FEED_CACHE_KEY, xml, 60 * 60)
    return ToolResult(output=stats, display=f'{stats["items"]} items, {stats["skipped"]} skipped')


@tool(
    name='meta.ads_report',
    description='Meta Ads campaign performance for the last N days (spend, clicks, purchases, ROAS). Requires Meta Ads connected.',
    scopes=['analytics.read'],
    schema={
        'type': 'object',
        'properties': {'days': {'type': 'integer', 'enum': [7, 14, 30], 'default': 30}},
    },
)
def meta_ads_report_tool(*, days: int = 30) -> ToolResult:
    from plugins.installed.meta_commerce.services.ads_api import campaign_report

    rep = campaign_report(days=days)
    if not rep.get('ok'):
        return ToolResult(output=rep, display=f'Meta Ads not connected ({rep.get("reason")})')
    t = rep['totals']
    return ToolResult(
        output=rep,
        display=f'{len(rep["campaigns"])} campaigns · spend {t["spend"]} · ROAS {t.get("roas") or "—"}',
    )

"""Google Shopping agent tools — let Linda audit + manage the Merchant feed."""

from __future__ import annotations

from morpheus.core import ToolResult, tool


@tool(
    name='google.feed_coverage',
    description='Audit Google Merchant feed eligibility: how many active products are Shopping-eligible and what attributes are missing (image, price, gtin/mpn, brand, google_product_category).',
    scopes=['catalog.read'],
    schema={
        'type': 'object',
        'properties': {
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 5000},
        },
    },
)
def google_feed_coverage_tool(*, limit: int | None = None) -> ToolResult:
    from plugins.installed.google_shopping.services.coverage import coverage_report

    rep = coverage_report(limit=limit)
    return ToolResult(
        output=rep,
        display=f'{rep["eligible"]}/{rep["total"]} eligible ({rep["eligible_pct"]}%)',
    )


@tool(
    name='google.feed_url',
    description='Return the public Google Merchant Center product feed URL to submit in Merchant Center.',
    scopes=['catalog.read'],
    schema={'type': 'object', 'properties': {}},
)
def google_feed_url_tool() -> ToolResult:
    from morpheus.core import site_base_url

    url = site_base_url().rstrip('/') + '/feeds/google-merchant.xml'
    return ToolResult(output={'url': url}, display=url)


@tool(
    name='google.rebuild_feed',
    description='Rebuild the Google Merchant feed now and report how many items were written and skipped.',
    scopes=['catalog.write'],
    schema={'type': 'object', 'properties': {}},
)
def google_rebuild_feed_tool() -> ToolResult:
    from django.core.cache import cache

    from plugins.installed.google_shopping.services.feed import build_feed
    from plugins.installed.google_shopping.views import FEED_CACHE_KEY

    xml, stats = build_feed()
    cache.set(FEED_CACHE_KEY, xml, 60 * 60)
    return ToolResult(
        output=stats,
        display=f'{stats["items"]} items, {stats["skipped"]} skipped',
    )


@tool(
    name='google.merchant_diagnostics',
    description='Live Merchant Center product status: active/pending/disapproved counts + the top item-level issues (why products are disapproved). Requires Google to be connected.',
    scopes=['catalog.read'],
    schema={'type': 'object', 'properties': {}},
)
def google_merchant_diagnostics_tool() -> ToolResult:
    from plugins.installed.google_shopping.services.content_api import product_statuses

    d = product_statuses()
    if not d.get('ok'):
        return ToolResult(output=d, display=f'Not connected ({d.get("reason")})')
    c = d['counts']
    return ToolResult(
        output=d,
        display=f'{c["active"]} active · {c["disapproved"]} disapproved · {len(d["issues"])} issue types',
    )


@tool(
    name='google.ads_report',
    description='Google Ads campaign performance for the last N days (cost, clicks, conversions, ROAS per campaign). Requires Google Ads to be connected in settings.',
    scopes=['analytics.read'],
    schema={
        'type': 'object',
        'properties': {'days': {'type': 'integer', 'enum': [7, 14, 30], 'default': 30}},
    },
)
def google_ads_report_tool(*, days: int = 30) -> ToolResult:
    from plugins.installed.google_shopping.services.ads_api import campaign_report

    rep = campaign_report(days=days)
    if not rep.get('ok'):
        return ToolResult(output=rep, display=f'Google Ads not connected ({rep.get("reason")})')
    t = rep['totals']
    return ToolResult(
        output=rep,
        display=f'{len(rep["campaigns"])} campaigns · cost {t["cost"]} · ROAS {t.get("roas") or "—"}',
    )

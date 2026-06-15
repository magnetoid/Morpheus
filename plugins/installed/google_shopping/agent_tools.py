"""Google Shopping agent tools — let Linda audit + manage the Merchant feed."""

from __future__ import annotations

from core.agents import ToolResult, tool


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
    from core.utils.site import site_base_url

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

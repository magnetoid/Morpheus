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
    name='reddit.book_communities',
    description='Recommended book-buyer subreddits to target with Reddit ads, grouped by genre (general, fantasy, sci-fi, romance, mystery, horror, YA, literary, comics, audiobooks). Pass a genre to narrow.',
    scopes=['analytics.read'],
    schema={
        'type': 'object',
        'properties': {'genre': {'type': 'string', 'description': 'Optional genre to narrow to.'}},
    },
)
def reddit_book_communities_tool(*, genre: str = '') -> ToolResult:
    from plugins.installed.reddit_ads.services.book_communities import (
        BOOK_COMMUNITIES,
        communities_for,
    )

    if genre:
        subs = communities_for(genre)
        return ToolResult(
            output={'genre': genre, 'subreddits': subs}, display=', '.join('r/' + s for s in subs)
        )
    return ToolResult(
        output={'by_genre': BOOK_COMMUNITIES},
        display=f'{sum(len(v) for v in BOOK_COMMUNITIES.values())} subreddits across {len(BOOK_COMMUNITIES)} genres',
    )


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

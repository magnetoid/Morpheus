"""The traffic-sources card on the Analytics landing (DashboardCard)."""

from __future__ import annotations


def sources_card(request) -> dict:
    """The last 7 days' visits and the channels that brought most of them."""
    from plugins.installed.analytics.visits import sources_report

    report = sources_report(days=7, by='channel', limit=4)
    total = report['totals']['visits']
    if not total:
        return {'empty': 'No visits counted in the last 7 days yet.'}
    return {
        'value': f'{total:,}',
        'caption': 'visits in the last 7 days',
        'rows': [(row['label'], f'{row["visits"]:,} · {row["share"]}%') for row in report['rows']],
    }

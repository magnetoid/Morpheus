"""The NPS card on the Analytics overview (DashboardCard)."""

from __future__ import annotations


def nps_card(request) -> dict:
    """The 90-day Net Promoter Score and how many answered."""
    from plugins.installed.post_purchase import analytics

    summary = analytics.nps_summary(90)
    if not summary['responses']:
        return {'empty': 'No survey answers in the last 90 days.'}
    nps = summary['nps']
    rate = summary['response_rate']
    return {
        'value': str(nps),
        'caption': 'Net Promoter Score, last 90 days',
        'tone': 'ok' if nps >= 30 else ('danger' if nps < 0 else ''),
        'rows': [
            ('Answers', summary['responses']),
            ('Response rate', f'{rate}%' if rate is not None else '—'),
            ('Promoters / detractors', f'{summary["promoters"]} / {summary["detractors"]}'),
        ],
    }

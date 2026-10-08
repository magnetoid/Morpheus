"""The eco-impact card on the Marketing overview (DashboardCard).

The whole merchant surface of this app is a summary, so it is a card; the
card links to the pledge list."""

from __future__ import annotations


def eco_impact_card(request) -> dict:
    from plugins.installed.eco_impact import services

    totals = services.store_totals()
    if not totals['contributors']:
        return {'empty': 'No shopper has pledged a tree yet.'}
    return {
        'value': str(totals['trees']),
        'caption': 'trees pledged by shoppers — you fulfil the planting',
        'rows': [
            ('Contributing orders', totals['contributors']),
            ('CO₂ offset', f'{totals["co2_offset_kg"]:,.0f} kg'),
        ],
    }

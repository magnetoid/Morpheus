"""Pinterest Ads (API v5) — campaign reporting (analytics) + management.

Reporting = list campaigns + their analytics columns. Management = PATCH status,
POST create. Budgets are micro-currency (1 unit = 1,000,000 micros).
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta

from django.utils import timezone

from .api import ads_connected, creds, get, patch, post

logger = logging.getLogger('morpheus.pinterest_commerce')

_MICROS = 1_000_000
_COLUMNS = 'SPEND_IN_DOLLAR,IMPRESSION_1,CLICKTHROUGH_1,TOTAL_CHECKOUT'


def campaign_report(*, days: int = 30) -> dict:
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected', 'campaigns': [], 'totals': {}}
    acct = creds()['ad_account_id']

    listed = get(f'ad_accounts/{acct}/campaigns', {'page_size': 100})
    if not listed.get('ok'):
        return {'ok': False, 'reason': listed.get('reason'), 'campaigns': [], 'totals': {}}
    items = listed['data'].get('items', []) or []
    names = {c.get('id'): c.get('name') for c in items}
    ids = [c.get('id') for c in items if c.get('id')]
    if not ids:
        return {'ok': True, 'campaigns': [], 'totals': {}, 'days': days}

    end = timezone.now().date()
    start = end - timedelta(days=int(days))
    analytics = get(
        f'ad_accounts/{acct}/campaigns/analytics',
        {
            'campaign_ids': ','.join(ids[:100]),
            'start_date': start.isoformat(),
            'end_date': end.isoformat(),
            'columns': _COLUMNS,
            'granularity': 'TOTAL',
        },
    )
    if not analytics.get('ok'):
        return {'ok': False, 'reason': analytics.get('reason'), 'campaigns': [], 'totals': {}}

    campaigns = []
    t_spend = t_clicks = t_impr = t_conv = 0.0
    rows = (
        analytics['data']
        if isinstance(analytics['data'], list)
        else analytics['data'].get('items', [])
    )
    for row in rows or []:
        m = row.get('metrics', row)
        cid = str(row.get('campaign_id') or row.get('CAMPAIGN_ID') or '')
        spend = _f(m.get('SPEND_IN_DOLLAR'))
        clicks = _f(m.get('CLICKTHROUGH_1'))
        impr = _f(m.get('IMPRESSION_1'))
        conv = _f(m.get('TOTAL_CHECKOUT'))
        campaigns.append(
            {
                'id': cid,
                'name': names.get(cid) or cid,
                'spend': round(spend, 2),
                'clicks': int(clicks),
                'impressions': int(impr),
                'conversions': round(conv, 1),
            }
        )
        t_spend += spend
        t_clicks += clicks
        t_impr += impr
        t_conv += conv
    totals = {
        'spend': round(t_spend, 2),
        'clicks': int(t_clicks),
        'impressions': int(t_impr),
        'conversions': round(t_conv, 1),
    }
    return {'ok': True, 'campaigns': campaigns, 'totals': totals, 'days': days}


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def set_campaign_status(campaign_id: str, status: str) -> dict:
    """status in {'ACTIVE','PAUSED'}."""
    if status not in ('ACTIVE', 'PAUSED'):
        return {'ok': False, 'reason': 'bad_status'}
    if not re.fullmatch(r'\d{1,30}', str(campaign_id) or ''):
        return {'ok': False, 'reason': 'bad_campaign_id'}
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    acct = creds()['ad_account_id']
    return patch(f'ad_accounts/{acct}/campaigns', [{'id': str(campaign_id), 'status': status}])


def create_campaign(*, name: str, daily_budget: float) -> dict:
    """Create a PAUSED catalog-sales campaign (daily budget in account currency)."""
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    if not name:
        return {'ok': False, 'reason': 'missing_name'}
    acct = creds()['ad_account_id']
    return post(
        f'ad_accounts/{acct}/campaigns',
        [
            {
                'name': name,
                'objective_type': 'CATALOG_SALES',
                'status': 'PAUSED',
                'daily_spend_cap': int(float(daily_budget) * _MICROS),
            }
        ],
    )

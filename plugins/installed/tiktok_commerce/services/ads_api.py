"""TikTok Marketing API — campaign reporting (insights) + management."""

from __future__ import annotations

import logging
import re

from .api import ads_connected, creds, get, post

logger = logging.getLogger('morpheus.tiktok_commerce')

_PRESETS = {7: 'LAST_7_DAYS', 14: 'LAST_14_DAYS', 30: 'LAST_30_DAYS'}
_METRICS = [
    'spend',
    'impressions',
    'clicks',
    'conversion',
    'complete_payment',
    'total_complete_payment_rate',
]


def campaign_report(*, days: int = 30) -> dict:
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected', 'campaigns': [], 'totals': {}}
    preset = _PRESETS.get(int(days), 'LAST_30_DAYS')
    adv = creds()['advertiser_id']
    res = get(
        'report/integrated/get/',
        {
            'advertiser_id': adv,
            'report_type': 'BASIC',
            'data_level': 'AUCTION_CAMPAIGN',
            'dimensions': '["campaign_id"]',
            'metrics': '["campaign_name","spend","impressions","clicks","conversion","complete_payment"]',
            'service_type': 'AUCTION',
            'lifetime': 'false',
            'query_lifetime': 'false',
            'data_range': preset,
        },
    )
    if not res.get('ok'):
        return {'ok': False, 'reason': res.get('reason'), 'campaigns': [], 'totals': {}}

    campaigns = []
    t_spend = t_clicks = t_impr = t_conv = 0.0
    for row in res['data'].get('list', []):
        dims = row.get('dimensions', {})
        m = row.get('metrics', {})
        spend = _f(m.get('spend'))
        clicks = _f(m.get('clicks'))
        impr = _f(m.get('impressions'))
        conv = _f(m.get('complete_payment')) or _f(m.get('conversion'))
        campaigns.append(
            {
                'id': dims.get('campaign_id'),
                'name': m.get('campaign_name') or dims.get('campaign_id'),
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
    """Enable/pause a campaign. status in {'ENABLE','DISABLE'}."""
    if status not in ('ENABLE', 'DISABLE'):
        return {'ok': False, 'reason': 'bad_status'}
    if not re.fullmatch(r'\d{1,30}', str(campaign_id) or ''):
        return {'ok': False, 'reason': 'bad_campaign_id'}
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    adv = creds()['advertiser_id']
    return post(
        'campaign/status/update/',
        {'advertiser_id': adv, 'campaign_ids': [str(campaign_id)], 'operation_status': status},
    )


def create_campaign(*, name: str, budget: float) -> dict:
    """Create a PAUSED product-sales campaign (daily budget in account currency)."""
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    if not name:
        return {'ok': False, 'reason': 'missing_name'}
    adv = creds()['advertiser_id']
    return post(
        'campaign/create/',
        {
            'advertiser_id': adv,
            'campaign_name': name,
            'objective_type': 'PRODUCT_SALES',
            'budget_mode': 'BUDGET_MODE_DAY',
            'budget': float(budget),
            'operation_status': 'DISABLE',
        },
    )

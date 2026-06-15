"""Meta Marketing API — campaign reporting (insights) + management.

REST over the Graph helper. Reporting via `/{ad_account_id}/insights`; management
via campaign status POST. Graceful no-op when not connected. Spend/values are in
the ad account currency.
"""

from __future__ import annotations

import contextlib
import logging
import re

from .graph import ads_connected, creds, get, post

logger = logging.getLogger('morpheus.meta_commerce')

_PRESETS = {7: 'last_7d', 14: 'last_14d', 30: 'last_30d'}


def campaign_report(*, days: int = 30) -> dict:
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected', 'campaigns': [], 'totals': {}}
    preset = _PRESETS.get(int(days), 'last_30d')
    acct = creds()['ad_account_id']
    res = get(
        f'act_{acct}/insights',
        {
            'level': 'campaign',
            'date_preset': preset,
            'fields': 'campaign_id,campaign_name,spend,impressions,clicks,actions,action_values',
            'limit': 200,
        },
    )
    if not res.get('ok'):
        return {'ok': False, 'reason': res.get('reason'), 'campaigns': [], 'totals': {}}

    campaigns = []
    t_spend = t_clicks = t_impr = t_purch = t_value = 0.0
    for row in res['data'].get('data', []):
        spend = float(row.get('spend', 0) or 0)
        clicks = float(row.get('clicks', 0) or 0)
        impr = float(row.get('impressions', 0) or 0)
        purch = _action(row.get('actions'), 'purchase')
        value = _action(row.get('action_values'), 'purchase')
        campaigns.append(
            {
                'id': row.get('campaign_id'),
                'name': row.get('campaign_name'),
                'spend': round(spend, 2),
                'clicks': int(clicks),
                'impressions': int(impr),
                'purchases': round(purch, 1),
                'value': round(value, 2),
                'roas': round(value / spend, 2) if spend else None,
            }
        )
        t_spend += spend
        t_clicks += clicks
        t_impr += impr
        t_purch += purch
        t_value += value
    totals = {
        'spend': round(t_spend, 2),
        'clicks': int(t_clicks),
        'impressions': int(t_impr),
        'purchases': round(t_purch, 1),
        'value': round(t_value, 2),
        'roas': round(t_value / t_spend, 2) if t_spend else None,
    }
    return {'ok': True, 'campaigns': campaigns, 'totals': totals, 'days': days}


def _action(actions, action_type: str) -> float:
    """Sum the value for a given action_type out of a Meta actions array."""
    if not actions:
        return 0.0
    total = 0.0
    for a in actions:
        if a.get('action_type', '').endswith(action_type):
            with contextlib.suppress(TypeError, ValueError):
                total += float(a.get('value', 0))
    return total


def set_campaign_status(campaign_id: str, status: str) -> dict:
    """Pause/activate a campaign. status in {'ACTIVE','PAUSED'}."""
    if status not in ('ACTIVE', 'PAUSED'):
        return {'ok': False, 'reason': 'bad_status'}
    # Campaign IDs are numeric. Validate before it becomes a Graph URL path so a
    # crafted POST value can't redirect the write to another Graph endpoint.
    if not re.fullmatch(r'\d{1,30}', str(campaign_id) or ''):
        return {'ok': False, 'reason': 'bad_campaign_id'}
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    return post(str(campaign_id), {'status': status})


def create_catalog_campaign(*, name: str, daily_budget: float) -> dict:
    """Create a PAUSED Advantage+ catalog (PRODUCT_CATALOG_SALES) campaign.

    Budget is in the account currency's minor units (cents) per the API.
    """
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    if not name:
        return {'ok': False, 'reason': 'missing_name'}
    acct = creds()['ad_account_id']
    return post(
        f'act_{acct}/campaigns',
        {
            'name': name,
            'objective': 'OUTCOME_SALES',
            'status': 'PAUSED',
            'special_ad_categories': '[]',
            'daily_budget': str(int(float(daily_budget) * 100)),
        },
    )

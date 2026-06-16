"""Amazon Sponsored Products campaign management (Ads API v3).

list / pause / enable / create over the v3 campaign endpoints (vendor media
types). Defensive parsing, graceful no-op when not connected. Performance metrics
come from the async Reporting API (services.reporting), not here.
"""

from __future__ import annotations

import logging
import re

from .api import ads_connected, request

logger = logging.getLogger('morpheus.amazon_ads')

# v3 Sponsored Products campaign media type.
_SP_V3 = 'application/vnd.spCampaign.v3+json'


def list_campaigns() -> dict:
    """POST /sp/campaigns/list → [{id, name, state, budget}]."""
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected', 'campaigns': []}
    res = request(
        'POST',
        '/sp/campaigns/list',
        json_body={
            'stateFilter': {'include': ['ENABLED', 'PAUSED', 'PROPOSED']},
            'maxResults': 200,
        },
        headers_extra={'Content-Type': _SP_V3, 'Accept': _SP_V3},
    )
    if not res.get('ok'):
        return {'ok': False, 'reason': res.get('reason'), 'campaigns': []}
    out = []
    for c in (res['data'] or {}).get('campaigns', []) or []:
        budget = c.get('budget') or {}
        out.append(
            {
                'id': str(c.get('campaignId') or ''),
                'name': c.get('name', ''),
                'state': c.get('state', ''),
                'budget': budget.get('budget') if isinstance(budget, dict) else budget,
            }
        )
    return {'ok': True, 'campaigns': [c for c in out if c['id']]}


def set_campaign_status(campaign_id: str, state: str) -> dict:
    """PUT /sp/campaigns — state in {'ENABLED','PAUSED'}."""
    if state not in ('ENABLED', 'PAUSED'):
        return {'ok': False, 'reason': 'bad_status'}
    if not re.fullmatch(r'\d{1,30}', str(campaign_id) or ''):
        return {'ok': False, 'reason': 'bad_campaign_id'}
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    res = request(
        'PUT',
        '/sp/campaigns',
        json_body={'campaigns': [{'campaignId': str(campaign_id), 'state': state}]},
        headers_extra={'Content-Type': _SP_V3, 'Accept': _SP_V3},
    )
    return {'ok': res.get('ok'), 'reason': res.get('reason')}


def set_campaign_budget(campaign_id: str, daily_budget: float) -> dict:
    """PUT /sp/campaigns — update an existing campaign's daily budget."""
    if not re.fullmatch(r'\d{1,30}', str(campaign_id) or ''):
        return {'ok': False, 'reason': 'bad_campaign_id'}
    try:
        amount = float(daily_budget)
    except (TypeError, ValueError):
        amount = 0.0
    if amount <= 0:
        return {'ok': False, 'reason': 'bad_budget'}
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    res = request(
        'PUT',
        '/sp/campaigns',
        json_body={
            'campaigns': [
                {
                    'campaignId': str(campaign_id),
                    'budget': {'budget': amount, 'budgetType': 'DAILY'},
                }
            ]
        },
        headers_extra={'Content-Type': _SP_V3, 'Accept': _SP_V3},
    )
    return {'ok': res.get('ok'), 'reason': res.get('reason')}


def create_campaign(*, name: str, daily_budget: float) -> dict:
    """POST /sp/campaigns — a PAUSED auto-targeted Sponsored Products campaign."""
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    if not name:
        return {'ok': False, 'reason': 'missing_name'}
    res = request(
        'POST',
        '/sp/campaigns',
        json_body={
            'campaigns': [
                {
                    'name': name,
                    'targetingType': 'AUTO',
                    'state': 'PAUSED',
                    'budget': {'budget': float(daily_budget), 'budgetType': 'DAILY'},
                    'dynamicBidding': {'strategy': 'LEGACY_FOR_SALES'},
                }
            ]
        },
        headers_extra={'Content-Type': _SP_V3, 'Accept': _SP_V3},
    )
    return {'ok': res.get('ok'), 'reason': res.get('reason')}

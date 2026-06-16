"""Microsoft Advertising — campaign MANAGEMENT over the SOAP Campaign Management
v13 API (list / pause / enable / create + budget).

Performance METRICS (spend/clicks/ROAS) are intentionally NOT here — those need
the async Reporting service (submit→poll→download→parse CSV), too brittle to
build unvalidated. Campaign control is the tractable, single-request SOAP half.
Every call degrades to {ok: False, reason} when not connected.
"""

from __future__ import annotations

import logging
import re
from xml.sax.saxutils import escape

from .soap import ads_connected, ads_creds, call, findall_local, text_of

logger = logging.getLogger('morpheus.microsoft_commerce')

# Campaign types we manage (Shopping + Performance Max cover catalog ads).
_CAMPAIGN_TYPES = 'Shopping Audience PerformanceMax Search DynamicSearchAds'


def list_campaigns() -> dict:
    """GetCampaignsByAccountId → [{id, name, status, budget}]. No metrics."""
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected', 'campaigns': []}
    acct = ads_creds()['account_id']
    res = call(
        'GetCampaignsByAccountId',
        f'<AccountId>{escape(acct)}</AccountId><CampaignType>{_CAMPAIGN_TYPES}</CampaignType>',
    )
    if not res.get('ok'):
        return {'ok': False, 'reason': res.get('reason'), 'campaigns': []}
    campaigns = []
    for camp in findall_local(res['root'], 'Campaign'):
        cid = text_of(camp, 'Id')
        if not cid:
            continue
        campaigns.append(
            {
                'id': cid,
                'name': text_of(camp, 'Name'),
                'status': text_of(camp, 'Status') or 'Unknown',
                'budget': text_of(camp, 'Amount') or text_of(camp, 'DailyBudget'),
            }
        )
    return {'ok': True, 'campaigns': campaigns}


# Reporting in this plugin == the campaign list (control surface), no metrics.
def campaign_report(*, days: int = 30) -> dict:  # noqa: ARG001 — days unused (no metrics)
    r = list_campaigns()
    if not r.get('ok'):
        return {'ok': False, 'reason': r.get('reason'), 'campaigns': [], 'totals': {}}
    return {'ok': True, 'campaigns': r['campaigns'], 'totals': {}, 'metrics_supported': False}


def set_campaign_status(campaign_id: str, status: str) -> dict:
    """UpdateCampaigns Status. status in {'Active','Paused'}."""
    if status not in ('Active', 'Paused'):
        return {'ok': False, 'reason': 'bad_status'}
    if not re.fullmatch(r'\d{1,30}', str(campaign_id) or ''):
        return {'ok': False, 'reason': 'bad_campaign_id'}
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    acct = ads_creds()['account_id']
    body = (
        f'<AccountId>{escape(acct)}</AccountId>'
        '<Campaigns>'
        f'<Campaign><Id>{escape(str(campaign_id))}</Id><Status>{status}</Status></Campaign>'
        '</Campaigns>'
    )
    res = call('UpdateCampaigns', body)
    return {'ok': res.get('ok'), 'reason': res.get('reason')}


def create_campaign(*, name: str, daily_budget: float) -> dict:
    """AddCampaigns — a PAUSED Shopping campaign (daily budget in account currency)."""
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    if not name:
        return {'ok': False, 'reason': 'missing_name'}
    acct = ads_creds()['account_id']
    body = (
        f'<AccountId>{escape(acct)}</AccountId>'
        '<Campaigns>'
        '<Campaign>'
        f'<Name>{escape(name)}</Name>'
        '<CampaignType>Shopping</CampaignType>'
        '<Status>Paused</Status>'
        f'<DailyBudget>{float(daily_budget)}</DailyBudget>'
        '<BudgetType>DailyBudgetStandard</BudgetType>'
        '</Campaign>'
        '</Campaigns>'
    )
    res = call('AddCampaigns', body)
    return {'ok': res.get('ok'), 'reason': res.get('reason')}

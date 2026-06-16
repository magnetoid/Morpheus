"""Reddit Ads campaign management + reporting (Ads API v3)."""

from __future__ import annotations

import logging
import re

from .api import ads_connected, creds, request

logger = logging.getLogger('morpheus.reddit_ads')

# Reddit ids are alphanumeric with underscores (e.g. "t2_…"), not pure digits.
_ID_RE = re.compile(r'^[A-Za-z0-9_]{3,60}$')


def _acct_path() -> str:
    return f'/api/v3/ad_accounts/{creds()["account_id"]}'


def list_campaigns() -> dict:
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected', 'campaigns': []}
    res = request('GET', f'{_acct_path()}/campaigns?page.size=200')
    if not res.get('ok'):
        return {'ok': False, 'reason': res.get('reason'), 'campaigns': []}
    data = (res['data'] or {}).get('data', []) or []
    out = []
    for c in data:
        out.append(
            {
                'id': str(c.get('id') or ''),
                'name': c.get('name', ''),
                'status': c.get('configured_status') or c.get('effective_status') or '',
                'objective': c.get('objective', ''),
            }
        )
    return {'ok': True, 'campaigns': [c for c in out if c['id']]}


def set_campaign_status(campaign_id: str, status: str) -> dict:
    """status in {'ACTIVE','PAUSED'}."""
    if status not in ('ACTIVE', 'PAUSED'):
        return {'ok': False, 'reason': 'bad_status'}
    if not _ID_RE.match(str(campaign_id) or ''):
        return {'ok': False, 'reason': 'bad_campaign_id'}
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    res = request(
        'PATCH',
        f'{_acct_path()}/campaigns/{campaign_id}',
        json_body={'data': {'configured_status': status}},
    )
    return {'ok': res.get('ok'), 'reason': res.get('reason')}


def create_campaign(*, name: str, daily_budget: float) -> dict:
    """Create a PAUSED conversions campaign. spend_cap is in micro-currency."""
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    if not name:
        return {'ok': False, 'reason': 'missing_name'}
    res = request(
        'POST',
        f'{_acct_path()}/campaigns',
        json_body={
            'data': {
                'name': name,
                'objective': 'CONVERSIONS',
                'configured_status': 'PAUSED',
                'spend_cap': int(float(daily_budget) * 1_000_000),
            }
        },
    )
    return {'ok': res.get('ok'), 'reason': res.get('reason')}


def campaign_report(*, days: int = 30) -> dict:
    """Campaign metrics via the reporting endpoint (spend/impressions/clicks/
    conversions). Defensive — Reddit's report shape varies; fail-soft."""
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected', 'campaigns': [], 'totals': {}}
    from datetime import timedelta

    from django.utils import timezone  # noqa: PLC0415

    end = timezone.now().date()
    start = end - timedelta(days=int(days))
    res = request(
        'POST',
        f'{_acct_path()}/reports',
        json_body={
            'data': {
                'breakdowns': ['CAMPAIGN_ID'],
                'fields': ['spend', 'impressions', 'clicks', 'conversion_purchase_total_items'],
                'starts_at': start.isoformat() + 'T00:00:00Z',
                'ends_at': end.isoformat() + 'T00:00:00Z',
                'time_zone_id': 'GMT',
            }
        },
    )
    if not res.get('ok'):
        return {'ok': False, 'reason': res.get('reason'), 'campaigns': [], 'totals': {}}
    rows = (res['data'] or {}).get('data', []) or []
    campaigns = []
    t_spend = t_clicks = t_impr = t_conv = 0.0
    for r in rows:
        spend = _f(r.get('spend')) / 1_000_000  # micros → currency
        clicks = _f(r.get('clicks'))
        impr = _f(r.get('impressions'))
        conv = _f(r.get('conversion_purchase_total_items'))
        campaigns.append(
            {
                'id': str(r.get('campaign_id') or r.get('CAMPAIGN_ID') or ''),
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

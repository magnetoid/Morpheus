"""Snapchat Marketing API — campaign management + stats reporting."""

from __future__ import annotations

import logging
import re

from .api import ads_connected, creds, request

logger = logging.getLogger('morpheus.snapchat_commerce')

# Snapchat ids are UUIDs (alphanumeric + hyphen).
_ID_RE = re.compile(r'^[A-Za-z0-9-]{6,64}$')


def _acct() -> str:
    return creds()['ad_account_id']


def list_campaigns() -> dict:
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected', 'campaigns': []}
    res = request('GET', f'/adaccounts/{_acct()}/campaigns')
    if not res.get('ok'):
        return {'ok': False, 'reason': res.get('reason'), 'campaigns': []}
    out = []
    for wrap in (res['data'] or {}).get('campaigns', []) or []:
        c = wrap.get('campaign') or wrap
        out.append(
            {
                'id': str(c.get('id') or ''),
                'name': c.get('name', ''),
                'status': c.get('status', ''),
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
        'PUT',
        f'/adaccounts/{_acct()}/campaigns',
        json_body={'campaigns': [{'id': str(campaign_id), 'status': status}]},
    )
    return {'ok': res.get('ok'), 'reason': res.get('reason')}


def create_campaign(*, name: str, daily_budget: float) -> dict:  # noqa: ARG001 — budget set on ad squad
    """Create a PAUSED campaign (objective on Snap = budgets live on ad squads,
    set after in Ads Manager — campaign create just names the objective)."""
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    if not name:
        return {'ok': False, 'reason': 'missing_name'}
    res = request(
        'POST',
        f'/adaccounts/{_acct()}/campaigns',
        json_body={'campaigns': [{'name': name, 'status': 'PAUSED', 'objective': 'SALES'}]},
    )
    return {'ok': res.get('ok'), 'reason': res.get('reason')}


def campaign_report(*, days: int = 30) -> dict:
    """Account stats broken down by campaign (spend, impressions, swipes,
    purchases). Defensive — Snap stats shape is nested; fail-soft."""
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected', 'campaigns': [], 'totals': {}}
    from datetime import timedelta

    from django.utils import timezone  # noqa: PLC0415

    end = timezone.now().date()
    start = end - timedelta(days=int(days))
    res = request(
        'GET',
        f'/adaccounts/{_acct()}/stats',
        params={
            'granularity': 'TOTAL',
            'breakdown': 'campaign',
            'fields': 'spend,impressions,swipes,conversion_purchases',
            'start_time': start.isoformat() + 'T00:00:00.000-00:00',
            'end_time': end.isoformat() + 'T00:00:00.000-00:00',
        },
    )
    if not res.get('ok'):
        return {'ok': False, 'reason': res.get('reason'), 'campaigns': [], 'totals': {}}

    campaigns = []
    t_spend = t_clicks = t_impr = t_conv = 0.0
    for row in _iter_stat_rows(res['data']):
        stats = row.get('stats') or row
        spend = _f(stats.get('spend')) / 1_000_000  # micro-currency
        swipes = _f(stats.get('swipes'))
        impr = _f(stats.get('impressions'))
        conv = _f(stats.get('conversion_purchases'))
        campaigns.append(
            {
                'id': str(row.get('id') or ''),
                'spend': round(spend, 2),
                'clicks': int(swipes),
                'impressions': int(impr),
                'conversions': round(conv, 1),
            }
        )
        t_spend += spend
        t_clicks += swipes
        t_impr += impr
        t_conv += conv
    totals = {
        'spend': round(t_spend, 2),
        'clicks': int(t_clicks),
        'impressions': int(t_impr),
        'conversions': round(t_conv, 1),
    }
    return {'ok': True, 'campaigns': campaigns, 'totals': totals, 'days': days}


def _iter_stat_rows(data):
    """Snap nests stats under total_stats[].total_stat.breakdown_stats.campaign[]
    — pull the per-campaign rows defensively from whatever shape is present."""
    if not isinstance(data, dict):
        return []
    for ts in data.get('total_stats', []) or []:
        stat = ts.get('total_stat') or ts
        bd = stat.get('breakdown_stats') or {}
        rows = bd.get('campaign') or bd.get('campaigns') or []
        if rows:
            return rows
    return data.get('timeseries_stats', []) or []


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0

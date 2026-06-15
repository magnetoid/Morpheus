"""Google Ads API (REST v17) — reporting + campaign management.

REST over `requests` + an OAuth2 access token (services.google_auth) + a
developer token — no google-ads SDK (which is gRPC + heavy). Two surfaces:

* **Reporting** — `customers/{cid}/googleAds:searchStream` with GAQL, returning
  campaign metrics (impressions, clicks, cost, conversions, value, ROAS).
* **Campaign management** — list / pause / enable campaigns and set budgets via
  the `campaigns:mutate` + `campaignBudgets:mutate` endpoints.

Every call degrades to a structured `{ok: False, reason: ...}` when the plugin
isn't connected, so the dashboard renders a "connect Google Ads" state instead
of erroring. Money is micros (1 unit = 1_000_000 micros) per the API.
"""

from __future__ import annotations

import contextlib
import logging

from .google_auth import access_token, is_connected
from .settings import raw_config

logger = logging.getLogger('morpheus.google_shopping')

_API = 'https://googleads.googleapis.com/v17'
_MICROS = 1_000_000


def ads_config() -> dict:
    cfg = raw_config()
    return {
        'developer_token': (cfg.get('ads_developer_token') or '').strip(),
        'customer_id': (cfg.get('ads_customer_id') or '').replace('-', '').strip(),
        'login_customer_id': (cfg.get('ads_login_customer_id') or '').replace('-', '').strip(),
    }


def ads_connected() -> bool:
    c = ads_config()
    return bool(is_connected() and c['developer_token'] and c['customer_id'])


def _headers() -> dict | None:
    token = access_token()
    if not token:
        return None
    c = ads_config()
    h = {'Authorization': f'Bearer {token}', 'developer-token': c['developer_token']}
    if c['login_customer_id']:
        h['login-customer-id'] = c['login_customer_id']
    return h


def _search(query: str) -> tuple[list[dict], str | None]:
    """Run a GAQL query via searchStream → (rows, error)."""
    if not ads_connected():
        return [], 'not_connected'
    headers = _headers()
    if headers is None:
        return [], 'no_access_token'
    c = ads_config()
    url = f'{_API}/customers/{c["customer_id"]}/googleAds:searchStream'
    try:
        import requests  # noqa: PLC0415

        resp = requests.post(url, json={'query': query}, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        logger.warning('google_shopping: ads search failed: %s', e)
        return [], str(e)[:200]
    rows: list[dict] = []
    # searchStream returns a list of {results: [...]} chunks.
    for chunk in data if isinstance(data, list) else [data]:
        rows.extend(chunk.get('results', []))
    return rows, None


def campaign_report(*, days: int = 30) -> dict:
    """Campaign metrics for the last N days."""
    # GAQL accepts only specific DURING presets; allowlist (never interpolate).
    preset = {7: 'LAST_7_DAYS', 14: 'LAST_14_DAYS', 30: 'LAST_30_DAYS'}.get(
        int(days), 'LAST_30_DAYS'
    )
    query = (
        'SELECT campaign.id, campaign.name, campaign.status, '
        'campaign.advertising_channel_type, metrics.impressions, metrics.clicks, '
        'metrics.cost_micros, metrics.conversions, metrics.conversions_value '
        'FROM campaign WHERE segments.date DURING ' + preset + ' '
        'ORDER BY metrics.cost_micros DESC'
    )
    rows, err = _search(query)
    if err:
        return {'ok': False, 'reason': err, 'campaigns': [], 'totals': {}}

    campaigns = []
    t_cost = t_clicks = t_impr = 0.0
    t_conv = t_value = 0.0
    for r in rows:
        camp = r.get('campaign', {})
        m = r.get('metrics', {})
        cost = float(m.get('costMicros', 0) or 0) / _MICROS
        clicks = float(m.get('clicks', 0) or 0)
        impr = float(m.get('impressions', 0) or 0)
        conv = float(m.get('conversions', 0) or 0)
        value = float(m.get('conversionsValue', 0) or 0)
        campaigns.append(
            {
                'id': camp.get('id'),
                'name': camp.get('name'),
                'status': camp.get('status'),
                'channel': camp.get('advertisingChannelType'),
                'cost': round(cost, 2),
                'clicks': int(clicks),
                'impressions': int(impr),
                'conversions': round(conv, 1),
                'value': round(value, 2),
                'roas': round(value / cost, 2) if cost else None,
            }
        )
        t_cost += cost
        t_clicks += clicks
        t_impr += impr
        t_conv += conv
        t_value += value
    totals = {
        'cost': round(t_cost, 2),
        'clicks': int(t_clicks),
        'impressions': int(t_impr),
        'conversions': round(t_conv, 1),
        'value': round(t_value, 2),
        'roas': round(t_value / t_cost, 2) if t_cost else None,
    }
    return {'ok': True, 'campaigns': campaigns, 'totals': totals, 'days': days}


def _mutate(resource: str, operations: list[dict]) -> dict:
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    headers = _headers()
    if headers is None:
        return {'ok': False, 'reason': 'no_access_token'}
    c = ads_config()
    url = f'{_API}/customers/{c["customer_id"]}/{resource}:mutate'
    try:
        import requests  # noqa: PLC0415

        resp = requests.post(url, json={'operations': operations}, headers=headers, timeout=30)
        resp.raise_for_status()
        return {'ok': True, 'result': resp.json()}
    except Exception as e:  # noqa: BLE001
        logger.warning('google_shopping: ads mutate failed: %s', e)
        return {'ok': False, 'reason': str(e)[:200]}


def set_campaign_status(campaign_id: str, status: str) -> dict:
    """Pause/enable a campaign. status in {'ENABLED','PAUSED'}."""
    if status not in ('ENABLED', 'PAUSED'):
        return {'ok': False, 'reason': 'bad_status'}
    c = ads_config()
    op = {
        'update': {
            'resourceName': f'customers/{c["customer_id"]}/campaigns/{campaign_id}',
            'status': status,
        },
        'updateMask': 'status',
    }
    return _mutate('campaigns', [op])


def set_campaign_budget(budget_id: str, daily_amount: float) -> dict:
    """Set a campaign budget's daily amount (in account currency units)."""
    c = ads_config()
    op = {
        'update': {
            'resourceName': f'customers/{c["customer_id"]}/campaignBudgets/{budget_id}',
            'amountMicros': str(int(float(daily_amount) * _MICROS)),
        },
        'updateMask': 'amount_micros',
    }
    return _mutate('campaignBudgets', [op])


def create_shopping_campaign(
    *, name: str, daily_budget: float, merchant_id: str, country: str = 'US'
) -> dict:
    """Create a (paused) Standard Shopping campaign tied to the Merchant feed.

    Two mutates: a campaign budget, then the campaign referencing it +
    shoppingSetting{merchantId, salesCountry}. Created PAUSED so nothing spends
    until the merchant reviews it in Google Ads. Returns {ok, campaign?}.
    """
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    if not (name and merchant_id):
        return {'ok': False, 'reason': 'missing_name_or_merchant'}

    budget_op = {
        'create': {
            'name': f'{name} budget',
            'amountMicros': str(int(float(daily_budget) * _MICROS)),
            'deliveryMethod': 'STANDARD',
        }
    }
    budget_res = _mutate('campaignBudgets', [budget_op])
    if not budget_res.get('ok'):
        return budget_res
    try:
        budget_rn = budget_res['result']['results'][0]['resourceName']
    except (KeyError, IndexError, TypeError):
        return {'ok': False, 'reason': 'budget_create_no_resource'}

    campaign_op = {
        'create': {
            'name': name,
            'advertisingChannelType': 'SHOPPING',
            'status': 'PAUSED',
            'campaignBudget': budget_rn,
            'shoppingSetting': {'merchantId': str(merchant_id), 'salesCountry': country or 'US'},
        }
    }
    res = _mutate('campaigns', [campaign_op])
    if res.get('ok'):
        with contextlib.suppress(KeyError, IndexError, TypeError):
            res['campaign'] = res['result']['results'][0]['resourceName']
    return res

"""Amazon Ads async Reporting (v3) — campaign performance metrics.

Async REST: POST /reporting/reports → poll GET /reporting/reports/{id} until
COMPLETED → download the GZIP-JSON from the returned url → parse. Runs in a
Celery task, caches the result. Fail-soft throughout — any wrong shape / timeout
/ bad gzip yields {ok: False, reason}, never a crash.

Best-effort until validated with live credentials (v3 report config + column
names are from the docs but unverified live).
"""

from __future__ import annotations

import logging

from .api import ads_connected, base_url, request

logger = logging.getLogger('morpheus.amazon_ads')

_CACHE_KEY = 'amazon_ads:metrics:v1'
_TTL = 60 * 60 * 6
_REPORT_V3 = 'application/vnd.createasyncreportrequest.v3+json'
_COLUMNS = ['campaignId', 'campaignName', 'cost', 'clicks', 'impressions', 'purchases7d', 'sales7d']


def _date(offset_days: int) -> str:
    from datetime import timedelta

    from django.utils import timezone  # noqa: PLC0415

    return (timezone.now().date() - timedelta(days=offset_days)).isoformat()


def _submit(days: int) -> str | None:
    body = {
        'name': 'MorpheusSPCampaigns',
        'startDate': _date(int(days)),
        'endDate': _date(0),
        'configuration': {
            'adProduct': 'SPONSORED_PRODUCTS',
            'groupBy': ['campaign'],
            'columns': _COLUMNS,
            'reportTypeId': 'spCampaigns',
            'timeUnit': 'SUMMARY',
            'format': 'GZIP_JSON',
        },
    }
    res = request(
        'POST',
        '/reporting/reports',
        json_body=body,
        headers_extra={'Content-Type': _REPORT_V3, 'Accept': _REPORT_V3},
    )
    if not res.get('ok'):
        return None
    return (res['data'] or {}).get('reportId')


def _poll(report_id: str, *, tries: int = 8, delay: float = 4.0) -> str | None:
    import time  # noqa: PLC0415

    for _ in range(tries):
        res = request('GET', f'/reporting/reports/{report_id}')
        if not res.get('ok'):
            return None
        data = res['data'] or {}
        status = data.get('status')
        if status == 'COMPLETED':
            return data.get('url')
        if status == 'FAILED':
            return None
        time.sleep(delay)
    return None


def _download_and_parse(url: str) -> dict:
    import gzip  # noqa: PLC0415
    import io  # noqa: PLC0415
    import json  # noqa: PLC0415

    import requests  # noqa: PLC0415

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    raw = resp.content
    try:
        text = gzip.GzipFile(fileobj=io.BytesIO(raw)).read().decode('utf-8', errors='replace')
    except OSError:
        text = raw.decode('utf-8', errors='replace')  # already-decompressed fallback
    rows = json.loads(text) if text.strip() else []
    out: dict[str, dict] = {}
    for r in rows if isinstance(rows, list) else []:
        cid = str(r.get('campaignId') or '')
        if not cid:
            continue
        out[cid] = {
            'cost': _f(r.get('cost')),
            'clicks': _f(r.get('clicks')),
            'impressions': _f(r.get('impressions')),
            'purchases': _f(r.get('purchases7d')),
            'sales': _f(r.get('sales7d')),
        }
    return out


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def fetch_metrics(*, days: int = 30) -> dict:
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    if not base_url():
        return {'ok': False, 'reason': 'no_region'}
    try:
        report_id = _submit(days)
        if not report_id:
            return {'ok': False, 'reason': 'submit_failed'}
        url = _poll(report_id)
        if not url:
            return {'ok': False, 'reason': 'report_not_ready'}
        return {'ok': True, 'metrics': _download_and_parse(url), 'days': days}
    except Exception as e:  # noqa: BLE001
        logger.warning('amazon_ads: reporting failed: %s', e)
        return {'ok': False, 'reason': str(e)[:200]}


def fetch_and_cache(*, days: int = 30) -> dict:
    from django.core.cache import cache  # noqa: PLC0415

    res = fetch_metrics(days=days)
    if res.get('ok'):
        cache.set(_CACHE_KEY, res, _TTL)
    return res


def cached_metrics() -> dict | None:
    from django.core.cache import cache  # noqa: PLC0415

    return cache.get(_CACHE_KEY)

"""Microsoft Advertising async Reporting (v13) — campaign performance metrics.

The Reporting service is async SOAP: SubmitGenerateReport → poll
PollGenerateReport until Success → download a ZIP → parse the CSV. This is the
brittle part of the Microsoft API (no clean REST), so EVERYTHING here is
fail-soft: any wrong shape / timeout / parse error yields {ok: False, reason}
(or 'metrics unavailable'), never a crash. Runs in a Celery task (never blocks a
request) and caches the parsed result for the dashboard.

BEST-EFFORT until validated against live credentials — the report-request XML,
poll fields and CSV column names are from the v13 docs but unverified live.
"""

from __future__ import annotations

import logging

from .soap import call, text_of

logger = logging.getLogger('morpheus.microsoft_commerce')

REPORTING_URL = (
    'https://reporting.api.bingads.microsoft.com/Api/Advertiser/Reporting/v13/ReportingService.svc'
)
_RNS = 'https://bingads.microsoft.com/Reporting/v13'
_CACHE_KEY = 'microsoft_commerce:ads_metrics:v1'
_TTL = 60 * 60 * 6
_TIME = {7: 'LastSevenDays', 14: 'LastFourteenDays', 30: 'LastThirtyDays'}

# CSV column → our metric key (defensive: we match on a normalised header).
_COLS = {
    'campaignid': 'campaign_id',
    'spend': 'spend',
    'impressions': 'impressions',
    'clicks': 'clicks',
    'conversions': 'conversions',
    'revenue': 'revenue',
}


def _report(action: str, body: str) -> dict:
    return call(action, body, url=REPORTING_URL, ns=_RNS)


def _submit(days: int, account_id: str) -> str | None:
    period = _TIME.get(int(days), 'LastThirtyDays')
    body = (
        '<ReportRequest i:type="CampaignPerformanceReportRequest">'
        '<Format>Csv</Format><ReportName>MorpheusCampaignPerf</ReportName>'
        '<ReturnOnlyCompleteData>false</ReturnOnlyCompleteData>'
        '<Aggregation>Summary</Aggregation>'
        f'<Scope><AccountIds xmlns:a="http://schemas.microsoft.com/2003/10/Serialization/Arrays">'
        f'<a:long>{account_id}</a:long></AccountIds></Scope>'
        '<Time><PredefinedTime>' + period + '</PredefinedTime></Time>'
        '<Columns>'
        '<CampaignPerformanceReportColumn>CampaignId</CampaignPerformanceReportColumn>'
        '<CampaignPerformanceReportColumn>Spend</CampaignPerformanceReportColumn>'
        '<CampaignPerformanceReportColumn>Impressions</CampaignPerformanceReportColumn>'
        '<CampaignPerformanceReportColumn>Clicks</CampaignPerformanceReportColumn>'
        '<CampaignPerformanceReportColumn>Conversions</CampaignPerformanceReportColumn>'
        '<CampaignPerformanceReportColumn>Revenue</CampaignPerformanceReportColumn>'
        '</Columns>'
        '</ReportRequest>'
    )
    res = _report('SubmitGenerateReport', body)
    if not res.get('ok'):
        return None
    return text_of(res['root'], 'ReportRequestId') or None


def _poll(request_id: str, *, tries: int = 6, delay: float = 3.0) -> str | None:
    import time  # noqa: PLC0415

    for _ in range(tries):
        res = _report('PollGenerateReport', f'<ReportRequestId>{request_id}</ReportRequestId>')
        if not res.get('ok'):
            return None
        status = text_of(res['root'], 'Status')
        if status == 'Success':
            return text_of(res['root'], 'ReportDownloadUrl') or None
        if status == 'Error':
            return None
        time.sleep(delay)
    return None


def _download_and_parse(url: str) -> dict:
    import csv  # noqa: PLC0415
    import io  # noqa: PLC0415
    import zipfile  # noqa: PLC0415

    import requests  # noqa: PLC0415

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    content = resp.content
    # The download is usually a ZIP; fall back to raw CSV bytes.
    text = ''
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            name = next((n for n in zf.namelist() if n.lower().endswith('.csv')), None)
            if name:
                text = zf.read(name).decode('utf-8-sig', errors='replace')
    except zipfile.BadZipFile:
        text = content.decode('utf-8-sig', errors='replace')
    if not text:
        return {}

    # Find the data header row (the one naming the columns) — Microsoft prepends
    # metadata rows, so scan for the row that contains a CampaignId-ish column.
    rows = list(csv.reader(io.StringIO(text)))
    header_idx = next(
        (i for i, r in enumerate(rows) if any(_norm(c) == 'campaignid' for c in r)), None
    )
    if header_idx is None:
        return {}
    header = [_norm(c) for c in rows[header_idx]]
    out: dict[str, dict] = {}
    for r in rows[header_idx + 1 :]:
        if len(r) != len(header):
            continue
        row = dict(zip(header, r, strict=False))
        cid = row.get('campaignid')
        if not cid:
            continue
        out[cid] = {
            'spend': _f(row.get('spend')),
            'impressions': _f(row.get('impressions')),
            'clicks': _f(row.get('clicks')),
            'conversions': _f(row.get('conversions')),
            'revenue': _f(row.get('revenue')),
        }
    return out


def _norm(s: str) -> str:
    return ''.join(ch for ch in (s or '').lower() if ch.isalnum())


def _f(v) -> float:
    try:
        return float(str(v).replace(',', '').replace('$', '') or 0)
    except (TypeError, ValueError):
        return 0.0


def fetch_metrics(*, days: int = 30) -> dict:
    """Run the full async report and return {campaign_id: metrics} — or
    {ok: False, reason}. Fail-soft throughout."""
    from .soap import ads_connected, ads_creds  # noqa: PLC0415

    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    try:
        request_id = _submit(days, ads_creds()['account_id'])
        if not request_id:
            return {'ok': False, 'reason': 'submit_failed'}
        url = _poll(request_id)
        if not url:
            return {'ok': False, 'reason': 'report_not_ready'}
        metrics = _download_and_parse(url)
        return {'ok': True, 'metrics': metrics, 'days': days}
    except Exception as e:  # noqa: BLE001 — reporting must never crash anything
        logger.warning('microsoft_commerce: reporting failed: %s', e)
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

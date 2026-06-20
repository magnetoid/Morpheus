"""Unified sales-channels overview — one operator page across every commerce
channel. Pure aggregator: collects a status row from each channel plugin via the
CHANNELS_OVERVIEW filter (cheap, per-page) and merges cached ads KPIs from the
daily channels.refresh_metrics task (no live API calls on page load)."""

from __future__ import annotations

import logging

from django.core.cache import cache

from morpheus.views import render, staff_member_required
from plugins.installed.channels.tasks import METRICS_CACHE_KEY

logger = logging.getLogger('morpheus.channels')

_CACHE_KEY = 'channels:overview:v1'
_TTL = 300


def _rows(*, refresh: bool = False) -> list[dict]:
    if not refresh:
        cached = cache.get(_CACHE_KEY)
        if cached is not None:
            return cached
    rows: list[dict] = []
    try:
        from core.hooks import MorpheusEvents, hook_registry  # noqa: PLC0415

        rows = hook_registry.filter(MorpheusEvents.CHANNELS_OVERVIEW, value=rows) or []
    except Exception as e:  # noqa: BLE001
        logger.warning('channels: overview filter failed: %s', e)
        rows = []
    rows = [r for r in rows if isinstance(r, dict) and r.get('name')]
    rows.sort(key=lambda r: r.get('label', '').lower())
    cache.set(_CACHE_KEY, rows, _TTL)
    return rows


def _merge_metrics(rows: list[dict]) -> bool:
    """Fold the daily-cached ads KPIs into each row. Returns True if KPIs exist."""
    metrics = cache.get(METRICS_CACHE_KEY)
    if not metrics:
        return False
    by_name = {m['name']: m for m in metrics if isinstance(m, dict) and m.get('name')}
    for r in rows:
        m = by_name.get(r['name'])
        if not m:
            continue
        spend = m.get('spend')
        revenue = m.get('revenue')
        roas = m.get('roas')
        if roas is None and revenue and spend:
            roas = round(revenue / spend, 2)
        r['metrics'] = {
            'spend': spend,
            'clicks': m.get('clicks'),
            'conversions': m.get('conversions'),
            'revenue': revenue,
            'roas': roas,
        }
    return True


@staff_member_required
def overview(request):
    msg = ''
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'refresh_metrics':
            from plugins.installed.channels.tasks import refresh_metrics  # noqa: PLC0415

            refresh_metrics.delay()
            msg = 'Refreshing channel KPIs in the background — check back shortly.'
        rows = _rows(refresh=action == 'refresh')
    else:
        rows = _rows()

    has_metrics = _merge_metrics(rows)
    connected = sum(1 for r in rows if r.get('connected'))
    feeds = sum(1 for r in rows if r.get('has_feed'))
    pixels = sum(1 for r in rows if r.get('pixel') == 'on')

    spend = _sum(rows, 'spend')
    conversions = _sum(rows, 'conversions')
    revenue = _sum(rows, 'revenue')
    return render(
        request,
        'channels/overview.html',
        {
            'active_nav': 'channels',
            'rows': rows,
            'has_metrics': has_metrics,
            'msg': msg,
            'totals': {
                'channels': len(rows),
                'connected': connected,
                'feeds': feeds,
                'pixels': pixels,
                'spend': round(spend, 2),
                'conversions': round(conversions, 1),
                'roas': round(revenue / spend, 2) if spend else None,
            },
        },
    )


def _sum(rows: list[dict], key: str) -> float:
    total = 0.0
    for r in rows:
        v = (r.get('metrics') or {}).get(key)
        if isinstance(v, int | float):
            total += v
    return total


@staff_member_required
def attribution_view(request):
    """Cross-channel attribution: blended MER + platform-claimed vs last-touch
    revenue per channel. Reads the daily-cached ads metrics + analytics."""
    from plugins.installed.channels.attribution import build_attribution

    try:
        days = int(request.GET.get('days', 30))
    except (TypeError, ValueError):
        days = 30
    if days not in (7, 14, 30, 90):
        days = 30

    msg = ''
    if request.method == 'POST' and request.POST.get('action') == 'refresh_metrics':
        from plugins.installed.channels.tasks import refresh_metrics

        refresh_metrics.delay()
        msg = 'Refreshing channel ad metrics in the background — check back shortly.'

    return render(
        request,
        'channels/attribution.html',
        {
            'active_nav': 'channels',
            'data': build_attribution(days=days),
            'days': days,
            'msg': msg,
        },
    )

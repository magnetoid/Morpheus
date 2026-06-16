"""Unified sales-channels overview — one operator page across every commerce
channel. Pure aggregator: collects a status row from each channel plugin via the
CHANNELS_OVERVIEW filter (no sibling-plugin imports, no live API calls)."""

from __future__ import annotations

import logging

from django.core.cache import cache

from morpheus.views import render, staff_member_required

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


@staff_member_required
def overview(request):
    refresh = request.method == 'POST' and request.POST.get('action') == 'refresh'
    rows = _rows(refresh=refresh)
    connected = sum(1 for r in rows if r.get('connected'))
    feeds = sum(1 for r in rows if r.get('has_feed'))
    pixels = sum(1 for r in rows if r.get('pixel') == 'on')
    return render(
        request,
        'channels/overview.html',
        {
            'active_nav': 'channels',
            'rows': rows,
            'totals': {
                'channels': len(rows),
                'connected': connected,
                'feeds': feeds,
                'pixels': pixels,
            },
        },
    )

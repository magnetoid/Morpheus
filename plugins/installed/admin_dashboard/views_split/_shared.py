"""Shared helpers used across the dashboard view modules."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

from morpheus.views import HttpRequest, HttpResponse, messages, staff_member_required
from morpheus.views import get_object_or_404, redirect, render
from django.utils import timezone

logger = logging.getLogger('morpheus.admin')

_PERIODS = {
    'today': 1,
    '7d': 7,
    '30d': 30,
    '90d': 90,
}


def _period(request: HttpRequest) -> tuple[str, int]:
    period = request.GET.get('period', '7d')
    if period not in _PERIODS:
        period = '7d'
    return period, _PERIODS[period]


def _since(days: int):
    return timezone.now() - timedelta(days=days)


@dataclass(slots=True)
class Metric:
    label: str
    value: str
    delta: str = ''
    trend: str = 'flat'  # 'up' | 'down' | 'flat'
    icon: str = 'activity'
    series: list = None  # last-14-days numeric series for sparkline


def _sparkline_points(series: list, width: int = 120, height: int = 28) -> tuple:
    """Convert a numeric series into an SVG `<polyline>` `points` string,
    plus the max value (used by the template to skip rendering on
    all-zero series). Caller passes `series` as a list of numbers oldest
    → newest. Returns ``("x1,y1 x2,y2 …", max_value)``.
    """
    if not series:
        return ('', 0)
    nums = [float(x or 0) for x in series]
    mx = max(nums)
    if mx <= 0 or len(nums) < 2:
        return ('', 0)
    n = len(nums)
    step = width / (n - 1)
    pts = []
    for i, v in enumerate(nums):
        x = round(i * step, 2)
        # Invert y because SVG origin is top-left. Add 2px top/bottom padding.
        y = round(height - 2 - (v / mx) * (height - 4), 2)
        pts.append(f'{x},{y}')
    return (' '.join(pts), mx)


def _trend(now, before) -> str:
    if not before:
        return 'flat'
    if now > before:
        return 'up'
    if now < before:
        return 'down'
    return 'flat'


def _pct_delta(now, before) -> str:
    if not before:
        return '—'
    diff = (Decimal(now) - Decimal(before)) / Decimal(before) * Decimal('100')
    sign = '+' if diff >= 0 else ''
    return f'{sign}{diff:.1f}%'


def _bulk_ids(request: HttpRequest, field: str = 'ids') -> list[str]:
    """Extract a sanitised list of UUID-like ids from POST.

    Caps at 500 so a runaway script can't ask us to delete 50k rows in
    one shot. Filters empty entries.
    """
    raw = request.POST.getlist(field)
    out = [s.strip() for s in raw if s and s.strip()]
    return out[:500]

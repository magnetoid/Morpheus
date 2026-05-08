"""Shared helpers used across the dashboard view modules."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from morpheus.views import HttpRequest, HttpResponse, messages, staff_member_required
from morpheus.views import get_object_or_404, redirect, render
from django.utils import timezone

logger = logging.getLogger('morpheus.admin')

# Display label + day-window for each preset. Order matters — it drives
# the order in the dashboard date-range picker dropdown.
DATE_PRESETS: list[tuple[str, str, int]] = [
    ('today',       'Today',          1),
    ('yesterday',   'Yesterday',      1),
    ('last5',       'Last 5 days',    5),
    ('7d',          'Last 7 days',    7),
    ('last14',      'Last 14 days',  14),
    ('30d',         'Last 30 days',  30),
    ('90d',         'Last 90 days',  90),
    ('this_month',  'This month',     0),  # computed
    ('last_month',  'Last month',     0),
    ('this_year',   'This year',      0),
    ('all_time',    'All time',       0),
]
_PRESET_LABELS = {key: label for key, label, _ in DATE_PRESETS}
_PRESET_DAYS = {key: days for key, _, days in DATE_PRESETS}

# Aliases kept so existing `?period=` links keep working.
_PERIOD_ALIASES = {'7d': '7d', '30d': '30d', '90d': '90d', 'today': 'today'}


@dataclass(slots=True)
class DateRange:
    """Resolved date window for a dashboard view.

    `start` / `end` bracket the current period (end is exclusive — i.e.
    the moment "right now"). `prev_start` / `prev_end` describe the
    same-length window immediately before, used for delta comparisons.
    `preset` is the key the UI passed in (or '' for a custom range).
    `label` is what the trigger button should show.
    """
    start: datetime
    end: datetime
    prev_start: datetime
    prev_end: datetime
    preset: str
    label: str
    days: int  # current-window length in days, for code that still wants an int

    @property
    def from_str(self) -> str:
        return self.start.date().isoformat()

    @property
    def to_str(self) -> str:
        return (self.end - timedelta(days=1)).date().isoformat()


def _parse_iso_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _resolve_date_range(request: HttpRequest) -> DateRange:
    """Pull the active date window off the query string.

    Accepts (in priority order):
      * `from=YYYY-MM-DD&to=YYYY-MM-DD` for a custom range
      * `preset=<key>` matching DATE_PRESETS
      * legacy `period=today|7d|30d|90d` (back-compat with old links)
    Falls back to `7d` so every view always gets a valid range.
    """
    now = timezone.now()
    today = now.date()

    custom_from = _parse_iso_date(request.GET.get('from', ''))
    custom_to = _parse_iso_date(request.GET.get('to', ''))
    if custom_from and custom_to:
        if custom_to < custom_from:
            custom_from, custom_to = custom_to, custom_from
        start_dt = _aware(datetime.combine(custom_from, time.min))
        end_dt = _aware(datetime.combine(custom_to + timedelta(days=1), time.min))
        days = max(1, (custom_to - custom_from).days + 1)
        prev_end = start_dt
        prev_start = prev_end - (end_dt - start_dt)
        label = f'{custom_from:%b %-d, %Y} – {custom_to:%b %-d, %Y}'
        return DateRange(start_dt, end_dt, prev_start, prev_end, '', label, days)

    preset = (request.GET.get('preset') or request.GET.get('period') or '7d').strip()
    if preset not in _PRESET_DAYS:
        preset = _PERIOD_ALIASES.get(preset, '7d')

    if preset == 'today':
        start_dt = _aware(datetime.combine(today, time.min))
        end_dt = now
    elif preset == 'yesterday':
        y = today - timedelta(days=1)
        start_dt = _aware(datetime.combine(y, time.min))
        end_dt = _aware(datetime.combine(today, time.min))
    elif preset == 'this_month':
        start_dt = _aware(datetime.combine(today.replace(day=1), time.min))
        end_dt = now
    elif preset == 'last_month':
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        start_dt = _aware(datetime.combine(last_prev.replace(day=1), time.min))
        end_dt = _aware(datetime.combine(first_this, time.min))
    elif preset == 'this_year':
        start_dt = _aware(datetime.combine(today.replace(month=1, day=1), time.min))
        end_dt = now
    elif preset == 'all_time':
        start_dt = _aware(datetime(2000, 1, 1, 0, 0, 0))
        end_dt = now
    else:
        # last5 / 7d / last14 / 30d / 90d — sliding day window
        days = _PRESET_DAYS[preset]
        start_dt = now - timedelta(days=days)
        end_dt = now

    days = max(1, (end_dt - start_dt).days or 1)
    prev_end = start_dt
    prev_start = prev_end - (end_dt - start_dt)
    label = _PRESET_LABELS.get(preset, preset)
    return DateRange(start_dt, end_dt, prev_start, prev_end, preset, label, days)


def _aware(dt: datetime) -> datetime:
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt


# ── Legacy helpers — kept so existing call sites compile unchanged. ────
_PERIODS = {'today': 1, '7d': 7, '30d': 30, '90d': 90}


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


def call_llm(prompt: str, system: str = '', max_tokens: int = 600) -> tuple[str, str]:
    """Single source of truth for "ask the configured AI provider for some
    text" from dashboard endpoints.

    Returns ``(text, error)``. On success, ``error`` is ''. On any failure
    (no provider configured, network glitch, gateway error) returns
    ``('', friendly_message)`` so the caller can return a clean JSON
    payload without needing per-route try/except.
    """
    try:
        from plugins.installed.ai_assistant.services.llm import get_llm
        gateway = get_llm()
    except Exception as e:  # noqa: BLE001 — provider not wired
        return ('', f'AI provider not configured: {e}')
    try:
        text = gateway.complete(
            prompt=prompt, system=system,
            temperature=0.6, max_tokens=max_tokens,
        )
    except Exception as e:  # noqa: BLE001
        return ('', f'AI provider error: {e}')
    return (text or '').strip(), ''

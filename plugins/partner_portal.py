"""The partner portal shell shared by the affiliate and the vendor portals.

Both portals are storefront pages a *partner* signs in to (``/affiliates/me/``,
``/vendor/me/``). They render inside the active theme and share one shell — an
identity header, a tab bar, KPI tiles, charts, tables and empty states — so a
partner sees the same product whichever programme they joined, and the shell is
written once instead of drifting in two copies.

This is shared *plugin infrastructure* (like ``plugins/feed_mapping.py`` and
``plugins/dropshipping/``): it knows nothing about affiliates or vendors. Each
app builds its own navigation and numbers and hands them to the shell through
the ``portal`` context; the templates live in ``plugins/templates/partner_portal/``
(``plugins`` is an installed app, so the app-directories loader finds them).

Numbers that reach CSS or SVG are formatted here as plain strings: a float
rendered by a template is localised (``42,5`` on a ``/sr/`` page), and
``height: 42,5%`` is no height at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone
from django.utils.dateformat import format as date_format
from django.utils.formats import number_format
from django.utils.translation import gettext as _

PERIOD_CHOICES = (7, 30, 90)
DEFAULT_PERIOD = 30
NOINDEX_REASON = 'partner portal'


@dataclass(frozen=True)
class Period:
    """The last ``days`` calendar days (today included) and the span before it."""

    days: int
    first_day: date
    start: datetime
    prev_start: datetime

    @property
    def dates(self) -> list[date]:
        return [self.first_day + timedelta(days=i) for i in range(self.days)]

    @property
    def label(self) -> str:
        return _('last %(days)s days') % {'days': self.days}


def period_from(request, default: int = DEFAULT_PERIOD) -> Period:
    """The period a portal page reports on, from ``?days=`` (7, 30 or 90)."""
    try:
        days = int(request.GET.get('days', default))
    except (TypeError, ValueError):
        days = default
    if days not in PERIOD_CHOICES:
        days = default
    first_day = timezone.localdate() - timedelta(days=days - 1)
    start = timezone.make_aware(datetime.combine(first_day, time.min))
    return Period(
        days=days, first_day=first_day, start=start, prev_start=start - timedelta(days=days)
    )


def period_links(period: Period) -> list[dict]:
    return [
        {
            'days': days,
            'label': _('%(days)s days') % {'days': days},
            'url': f'?days={days}',
            'active': days == period.days,
        }
        for days in PERIOD_CHOICES
    ]


def change(current, previous) -> dict | None:
    """How ``current`` moved against ``previous``, for a KPI tile.

    ``None`` when both are zero (nothing to compare). From zero to something is
    "new", never an infinite percentage.
    """
    cur = Decimal(str(current or 0))
    prev = Decimal(str(previous or 0))
    if cur == 0 and prev == 0:
        return None
    if prev == 0:
        return {'dir': 'up', 'text': _('new')}
    pct = int(((cur - prev) / prev * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    direction = 'up' if pct > 0 else 'down' if pct < 0 else 'flat'
    return {'dir': direction, 'text': f'{abs(pct)}%'}


def change_points(current: Decimal, previous: Decimal) -> dict | None:
    """A rate's move in percentage points (a rate's percent change misleads)."""
    if not current and not previous:
        return None
    diff = (Decimal(str(current)) - Decimal(str(previous))).quantize(Decimal('0.1'))
    direction = 'up' if diff > 0 else 'down' if diff < 0 else 'flat'
    points = number_format(abs(diff), decimal_pos=1)
    return {'dir': direction, 'text': _('%(points)s pts') % {'points': points}}


def rate(part, whole) -> Decimal:
    """``part / whole`` as a percentage with one decimal; 0 when ``whole`` is 0."""
    if not whole:
        return Decimal('0')
    return (Decimal(part) * 100 / Decimal(whole)).quantize(Decimal('0.1'))


def daily(rows, period: Period) -> list:
    """Spread ``{date: value}`` over every day of ``period`` (missing days are 0)."""
    by_day = dict(rows)
    return [by_day.get(day, 0) or 0 for day in period.dates]


def sparkline(values, *, width: int = 100, height: int = 32) -> dict:
    """SVG geometry for a KPI tile's trend line (``viewBox 0 0 width height``)."""
    nums = [float(v or 0) for v in values]
    if len(nums) < 2 or max(nums) <= 0:
        return {}
    peak = max(nums)
    step = width / (len(nums) - 1)
    pts = [(i * step, height - 2 - (v / peak) * (height - 4)) for i, v in enumerate(nums)]
    line = ' '.join(f'{x:.2f},{y:.2f}' for x, y in pts)
    area = (
        f'M0,{height} L' + ' L'.join(f'{x:.2f},{y:.2f}' for x, y in pts) + f' L{width},{height} Z'
    )
    return {'points': line, 'area': area, 'width': width, 'height': height}


def bar_chart(values, period: Period, *, fmt=str, highlight=None) -> dict:
    """Bars for a daily series: heights as percentage strings, a tip per bar and
    the axis labels. ``highlight`` is an optional parallel list of booleans."""
    nums = list(values)
    peak = max(nums) if nums else 0
    dates = period.dates
    bars = []
    for i, (day, value) in enumerate(zip(dates, nums, strict=False)):
        height = float(value) / float(peak) * 100 if peak else 0
        bars.append(
            {
                'h': f'{height:.1f}',
                'tip': f'{date_format(day, "M j")} · {fmt(value)}',
                'zero': not value,
                'hi': bool(highlight[i]) if highlight else False,
            }
        )
    total = sum(nums) if nums else 0
    return {
        'bars': bars,
        'count': len(bars),
        'peak': fmt(peak) if peak else '',
        'half': fmt(peak / 2) if peak else '',
        'first': date_format(dates[0], 'M j') if dates else '',
        'middle': date_format(dates[len(dates) // 2], 'M j') if dates else '',
        'last': _('Today'),
        'total': fmt(total),
        'empty': not peak,
    }


def initials(text: str) -> str:
    words = [w for w in str(text or '').replace('@', ' ').replace('-', ' ').split() if w]
    letters = ''.join(w[0] for w in words[:2]).upper()
    return letters or '·'


def nav_items(items, active: str) -> list[dict]:
    """``items`` are ``(key, label, url[, badge[, badge_tone]])`` tuples, in tab order."""
    out = []
    for item in items:
        key, label, url = item[0], item[1], item[2]
        out.append(
            {
                'key': key,
                'label': label,
                'url': url,
                'active': key == active,
                'badge': item[3] if len(item) > 3 else None,
                'badge_tone': item[4] if len(item) > 4 else '',
            }
        )
    return out


def portal_context(
    *,
    kind: str,
    kicker: str,
    name: str,
    title: str,
    sub: str = '',
    status: dict | None = None,
    nav=(),
    active: str = '',
    nav_label: str = '',
    actions=(),
    avatar_url: str = '',
) -> dict:
    """The template context every portal page carries.

    ``status`` is ``{'key', 'label', 'tone'}`` with tone ok | wait | bad | neutral;
    ``actions`` are ``{'label', 'url'}`` links beside it.
    ``seo_noindex_reason`` keeps the page out of search through the head
    document — one robots tag, from the seo app — instead of a second raw
    ``<meta name="robots">`` in the template.
    """
    return {
        'portal': {
            'kind': kind,
            'kicker': kicker,
            'name': name,
            'sub': sub,
            'initials': initials(name),
            'avatar_url': avatar_url,
            'status': status,
            'nav': nav_items(nav, active),
            'nav_label': nav_label,
            'actions': list(actions),
        },
        'seo_title': title,
        'seo_noindex_reason': NOINDEX_REASON,
    }

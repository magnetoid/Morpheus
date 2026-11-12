"""Dashboard-home contributions (DASHBOARD_KPIS / ACTIVITY_FEED filters).

Everything reads DailyMetric / recent AnalyticsEvent rows — indexed, cheap,
no raw event scans on the home render. Registered from plugin.ready(), so a
disabled plugin contributes nothing (hook bus gates on active state).
"""

from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Sum
from django.utils import timezone

from core.utils.site import store_today


def _period(date_range, today: date) -> tuple[date, date]:
    """The store days a dashboard range covers: a rolling range is its number
    of whole days ending today, a named one is read on the store's calendar.

    The range arrives as UTC instants, and reading those as dates gave "Last 7
    days" eight days (the eighth also in the comparison) and "Today" in New
    York yesterday as well."""
    preset = getattr(date_range, 'preset', None)
    if preset == '':  # a custom range names its own days
        return date_range.start.date(), (date_range.end - timedelta(days=1)).date()
    month = today.replace(day=1)
    yesterday = today - timedelta(days=1)
    named = {
        'yesterday': (yesterday, yesterday),
        'this_month': (month, today),
        'last_month': ((month - timedelta(days=1)).replace(day=1), month - timedelta(days=1)),
        'this_year': (today.replace(month=1, day=1), today),
        'all_time': (date_range.start.date(), today),
    }
    if preset in named:
        return named[preset]
    days = max(1, int(getattr(date_range, 'days', 1) or 1))  # today, 7d, 30d, …
    return today - timedelta(days=days - 1), today


def _total(first: date, last: date, metric: str, **filters) -> int:
    from plugins.installed.analytics.models import DailyMetric  # noqa: PLC0415

    if not any(k.startswith('dimension') for k in filters):
        filters['dimension'] = ''
    agg = DailyMetric.objects.filter(
        day__gte=first, day__lte=last, metric=metric, **filters
    ).aggregate(n=Sum('value_int'))
    return int(agg['n'] or 0)


def _window(date_range):
    """(current, previous) store-day windows: the dashboard's range when it
    sends one, else today, each against as many days just before it, which
    never overlap. The tiles used to show yesterday whatever range was picked."""
    today = store_today()
    first = last = today
    if date_range is not None and getattr(date_range, 'start', None):
        first, last = _period(date_range, today)
    length = last - first + timedelta(days=1)
    return (first, last), (first - length, first - timedelta(days=1))


def on_dashboard_kpis(value, date_range=None, **kwargs):
    """Visits, conversion rate and AI referrals for the dashboard's range, each
    against the period before it. Today's numbers are rolled every hour."""
    (first, last), (prev_first, prev_last) = _window(date_range)
    label = getattr(date_range, 'label', '') or 'today'

    visits, visits_prior = (
        _total(first, last, 'sessions'),
        _total(prev_first, prev_last, 'sessions'),
    )
    delta = ''
    trend = 'flat'
    if visits_prior:
        pct = (visits - visits_prior) / visits_prior * 100
        delta = f'{pct:+.0f}%'
        trend = 'up' if pct > 0 else ('down' if pct < 0 else 'flat')
    value.append(
        {
            'label': 'Visits',
            'value': f'{visits:,}',
            'delta': delta,
            'trend': trend,
            'icon': 'activity',
            'series': None,
            'hint': f'Visits by counted visitors, {label}. A visit ends after 30 minutes without a page.',
        }
    )

    def _rate(a, b) -> float:
        visits_in = _total(a, b, 'sessions')
        return _total(a, b, 'counted_purchases') / visits_in * 100 if visits_in else 0.0

    conv, conv_prior = _rate(first, last), _rate(prev_first, prev_last)
    value.append(
        {
            'label': 'Conversion rate',
            'value': f'{conv:.2f}%',
            'delta': f'{conv - conv_prior:+.2f}pp' if conv_prior else '',
            'trend': 'up' if conv >= conv_prior else 'down',
            'icon': 'target',
            'series': None,
            'hint': f'Purchases by counted visitors over their visits, {label}.',
        }
    )

    ai_visits = _total(first, last, 'top_sources', dimension__startswith='ai:')
    value.append(
        {
            'label': 'AI referrals',
            'value': f'{ai_visits:,}',
            'delta': '',
            'trend': 'flat',
            'icon': 'bot',
            'series': None,
            'hint': f'Visits that came from AI assistants (ChatGPT, Perplexity, …), {label}.',
        }
    )
    return value


def on_activity_feed(value, limit=20, **kwargs):
    """Recent metric anomalies (analytics.anomaly events from the nightly
    detector) as activity items."""
    from plugins.installed.analytics.models import AnalyticsEvent  # noqa: PLC0415

    since = timezone.now() - timedelta(days=7)
    for evt in AnalyticsEvent.objects.filter(
        name='analytics.anomaly', created_at__gte=since
    ).order_by('-created_at')[:5]:
        p = evt.payload or {}
        metric = p.get('metric', 'metric')
        direction = p.get('direction', 'moved')
        value.append(
            {
                'kind': 'anomaly',
                'icon': 'alert-triangle',
                'label': f'{metric} anomaly — {direction}',
                'hint': p.get('summary', ''),
                'url': '/dashboard/analytics/v2/',
                'when': evt.created_at,
            }
        )
    return value

"""Dashboard-home contributions (DASHBOARD_KPIS / ACTIVITY_FEED filters).

Everything reads DailyMetric / recent AnalyticsEvent rows — indexed, cheap,
no raw event scans on the home render. Registered from plugin.ready(), so a
disabled plugin contributes nothing (hook bus gates on active state).
"""

from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Sum
from django.utils import timezone

from core.utils.site import store_timezone, store_today


def _days(start, end) -> tuple[date, date]:
    """A dashboard window (``end`` exclusive) as the store's first and last day."""
    tz = store_timezone()
    return start.astimezone(tz).date(), (end - timedelta(microseconds=1)).astimezone(tz).date()


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
    sends one, else today against yesterday. The tiles used to show yesterday
    whatever range was picked."""
    if date_range is not None and getattr(date_range, 'start', None):
        return _days(date_range.start, date_range.end), _days(
            date_range.prev_start, date_range.prev_end
        )
    today = store_today()
    yesterday = today - timedelta(days=1)
    return (today, today), (yesterday, yesterday)


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
            'hint': f'Visitors referred by AI assistants (ChatGPT, Perplexity, …), {label}.',
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

"""Dashboard-home contributions (DASHBOARD_KPIS / ACTIVITY_FEED filters).

Everything reads DailyMetric / recent AnalyticsEvent rows — indexed, cheap,
no raw event scans on the home render. Registered from plugin.ready(), so a
disabled plugin contributes nothing (hook bus gates on active state).
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone


def _metric(day, name) -> int:
    from plugins.installed.analytics.models import DailyMetric  # noqa: PLC0415

    row = DailyMetric.objects.filter(day=day, metric=name, dimension='').first()
    return row.value_int if row else 0


def on_dashboard_kpis(value, date_range=None, **kwargs):
    """Sessions + conversion rate (yesterday's rollup, delta vs the day
    before) and AI-referred sessions over the trailing 7 rolled days."""
    from plugins.installed.analytics.models import DailyMetric  # noqa: PLC0415

    yday = timezone.now().date() - timedelta(days=1)
    prior = yday - timedelta(days=1)

    sessions, sessions_prior = _metric(yday, 'sessions'), _metric(prior, 'sessions')
    delta = ''
    trend = 'flat'
    if sessions_prior:
        pct = (sessions - sessions_prior) / sessions_prior * 100
        delta = f'{pct:+.0f}%'
        trend = 'up' if pct > 0 else ('down' if pct < 0 else 'flat')
    value.append(
        {
            'label': 'Sessions',
            'value': f'{sessions:,}',
            'delta': delta,
            'trend': trend,
            'icon': 'activity',
            'series': None,
            'hint': 'Consented visitor sessions yesterday (daily rollup).',
        }
    )

    conv_bp = _metric(yday, 'conversion_rate')
    conv_prior = _metric(prior, 'conversion_rate')
    conv_delta = f'{(conv_bp - conv_prior) / 100:+.2f}pp' if conv_prior else ''
    value.append(
        {
            'label': 'Conversion rate',
            'value': f'{conv_bp / 100:.2f}%',
            'delta': conv_delta,
            'trend': 'up' if conv_bp >= conv_prior else 'down',
            'icon': 'target',
            'series': None,
            'hint': 'Purchases / sessions yesterday.',
        }
    )

    week_ago = yday - timedelta(days=6)
    ai_sessions = sum(
        row.value_int
        for row in DailyMetric.objects.filter(
            day__gte=week_ago, metric='top_sources', dimension__startswith='ai:'
        )
    )
    value.append(
        {
            'label': 'AI referrals',
            'value': f'{ai_sessions:,}',
            'delta': '',
            'trend': 'flat',
            'icon': 'bot',
            'series': None,
            'hint': 'Sessions referred by AI assistants (ChatGPT, Perplexity, …), last 7 days.',
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

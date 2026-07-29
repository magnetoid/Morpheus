"""Observability plugin manifest."""

from __future__ import annotations

from celery.schedules import crontab

from morpheus.plugin import DashboardPage, Plugin


class ObservabilityPlugin(Plugin):
    name = 'observability'
    label = 'Observability'
    version = '0.2.0'
    description = 'Per-merchant metrics rollups, error log, and the audit-log surface.'
    has_models = True

    def ready(self) -> None:
        self.register_graphql_extension(
            'plugins.installed.observability.graphql.queries',
        )
        self.register_urls(
            'plugins.installed.observability.urls',
            prefix='dashboard/observability/',
            namespace='observability',
        )
        self._register_beat_schedule()

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Audit log',
                slug='audit',
                view='plugins.installed.observability.views.audit_log_view',
                icon='scroll-text',
                section='developer',
                order=80,
                url='/dashboard/observability/audit/',
            ),
        ]

    def _register_beat_schedule(self) -> None:
        from django.conf import settings

        schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', None)
        if schedule is None:
            return
        schedule.setdefault(
            'observability.rollup_hourly',
            {
                'task': 'plugins.installed.observability.tasks.rollup_metrics',
                'schedule': crontab(minute=5),
                'kwargs': {'granularity': 'hour', 'lookback_hours': 6},
            },
        )
        schedule.setdefault(
            'observability.rollup_daily',
            {
                'task': 'plugins.installed.observability.tasks.rollup_metrics',
                'schedule': crontab(hour=0, minute=15),
                'kwargs': {'granularity': 'day', 'lookback_hours': 36},
            },
        )

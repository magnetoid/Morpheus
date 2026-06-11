"""Observability plugin manifest."""

from __future__ import annotations

from celery.schedules import crontab

from morpheus import Plugin


class ObservabilityPlugin(Plugin):
    name = 'observability'
    label = 'Observability'
    version = '0.1.0'
    description = 'Per-merchant metrics rollups + error log dashboard.'
    has_models = True

    def ready(self) -> None:
        self.register_graphql_extension(
            'plugins.installed.observability.graphql.queries',
        )
        self._register_beat_schedule()

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

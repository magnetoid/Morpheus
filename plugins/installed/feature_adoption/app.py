"""feature_adoption — per-install feature usage + install health.

Single-install analytics: how much each plugin's surfaces get used, and a
0–100 health score. No fleet telemetry, no PII, no per-event rows. Everything
is contributed (context processor, TOOL_CALLING subscriber, DashboardPage,
DASHBOARD_KPIS tile), so it is disable- and delete-safe by construction.
"""

from __future__ import annotations

from morpheus.app import DashboardCard, DashboardPage, Plugin


class FeatureAdoptionPlugin(Plugin):
    name = 'feature_adoption'
    label = 'Feature adoption'
    version = '1.0.0'
    description = (
        'Per-install feature-usage aggregates (no PII) and an install-health score. '
        'Tracks dashboard and agent-tool surfaces by owning plugin.'
    )
    has_models = True

    def ready(self) -> None:
        from core.agents.events import AgentEvents
        from core.hooks import MorpheusEvents
        from plugins.installed.feature_adoption import tracking

        # Serve-time instrumentation (both fail-soft, ~0 cost).
        self.register_context_processor(tracking.track_dashboard_hit)
        self.register_hook(AgentEvents.TOOL_CALLING, tracking.track_agent_tool)

        # Health tile on the dashboard home KPI row.
        self.register_hook(MorpheusEvents.DASHBOARD_KPIS, tracking.dashboard_kpis, priority=80)

        # Hourly flush of cache counters → FeatureUsageDay.
        self.register_celery_tasks('plugins.installed.feature_adoption.tasks')
        self.register_celery_beat(
            'feature_adoption.flush',
            {
                # The registered NAME, not the module path: beat sends by name and
                # the worker rejected the module path as unregistered, so no store
                # ever got a FeatureUsageDay row (core/tests/test_beat_schedule.py).
                'task': 'feature_adoption.flush_usage_counters',
                'schedule': 60 * 60,
            },
        )

    def contribute_dashboard_cards(self) -> list:
        # A card on the Analytics landing, beside other apps' cards.
        return [
            DashboardCard(
                section='analytics',
                title='Feature adoption',
                data='plugins.installed.feature_adoption.cards.adoption_card',
                url='/dashboard/apps/feature_adoption/adoption/',
                cta='Open report',
                icon='activity',
                order=80,
                capability='analytics.read',
            )
        ]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Feature adoption',
                slug='adoption',
                view='plugins.installed.feature_adoption.views.adoption_dashboard',
                icon='activity',
                section='analytics',
                order=80,
                nav='hidden',
            )
        ]

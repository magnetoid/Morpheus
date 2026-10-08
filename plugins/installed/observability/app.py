"""Observability plugin manifest."""

from __future__ import annotations

from morpheus.app import DashboardPage, Plugin


class ObservabilityPlugin(Plugin):
    name = 'observability'
    label = 'Observability'
    version = '0.3.0'
    description = 'The audit-log surface and the error log.'
    has_models = True

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.observability.urls',
            prefix='dashboard/observability/',
            namespace='observability',
        )

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Audit log',
                slug='audit',
                view='plugins.installed.observability.views.audit_log_view',
                icon='scroll-text',
                section='team',
                order=30,
                url='/dashboard/observability/audit/',
                hint='Who changed what, and when',
                nav='settings',
            ),
        ]

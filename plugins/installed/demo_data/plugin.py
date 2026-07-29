"""Demo data plugin manifest."""

from __future__ import annotations

from morpheus.plugin import DashboardPage, Plugin


class DemoDataPlugin(Plugin):
    name = 'demo_data'
    label = 'Demo Data'
    version = '0.3.0'
    description = (
        'Idempotent seed data for the bookstore demo + on-demand random '
        'product generator themed by the active storefront theme.'
    )
    has_models = False
    requires_plugins: list[str] = []

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.demo_data.urls',
            prefix='dashboard/apps/demo_data/',
            namespace='demo_data',
        )

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                slug='index',
                label='Demo data',
                section='data',
                icon='database',
                view='plugins.installed.demo_data.views.demo_data_index',
                order=20,
                nav='settings',
            ),
        ]

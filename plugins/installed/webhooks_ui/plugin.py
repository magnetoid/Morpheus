"""Webhooks UI plugin manifest."""
from __future__ import annotations

from morpheus import Plugin
from morpheus import DashboardPage


class WebhooksUiPlugin(Plugin):
    name = 'webhooks_ui'
    label = 'Webhooks'
    version = '1.0.0'
    description = (
        'Merchant-facing CRUD for WebhookEndpoint + a delivery log with '
        'retry/replay for failed deliveries. Adds a celery task that signs '
        'and POSTs payloads with HMAC-SHA256.'
    )
    has_models = True

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.webhooks_ui.urls',
            prefix='dashboard/webhooks/',
            namespace='webhooks_ui',
        )
        self.register_celery_tasks('plugins.installed.webhooks_ui.tasks')

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Webhooks', slug='endpoints',
                view='plugins.installed.webhooks_ui.views.endpoints_list',
                icon='webhook', section='developer', order=10,
                nav='settings',
            ),
            DashboardPage(
                label='Deliveries', slug='deliveries',
                view='plugins.installed.webhooks_ui.views.deliveries_list',
                icon='list', section='developer', order=20,
                nav='settings',
            ),
        ]

"""Webhooks UI plugin manifest."""

from __future__ import annotations

from morpheus.app import DashboardPage, Plugin
from morpheus.core import events


def _take_delivery(value, endpoint=None, event_name='', payload=None, **_):
    """WEBHOOK_DELIVER: log the delivery and queue it (retries, dead-letter,
    replay). Core decided when and to whom; this only delivers."""
    if value or endpoint is None:
        return value
    from plugins.installed.webhooks_ui.services import enqueue_delivery

    enqueue_delivery(endpoint=endpoint, event_name=event_name, payload=payload or {})
    return True


class WebhooksUiPlugin(Plugin):
    name = 'webhooks_ui'
    label = 'Webhooks'
    version = '1.0.0'
    description = (
        'Merchant-facing CRUD for WebhookEndpoint + a delivery log with '
        'retry/replay for failed deliveries. Adds a celery task that signs '
        "and POSTs payloads with HMAC-SHA256. Takes each delivery core's "
        'dispatcher makes, so every attempt is logged and replayable.'
    )
    has_models = True

    def ready(self) -> None:
        self.register_hook(events.DASHBOARD_SEARCH, self.on_dashboard_search)
        self.register_urls(
            'plugins.installed.webhooks_ui.urls',
            prefix='dashboard/webhooks/',
            namespace='webhooks_ui',
        )
        self.register_celery_tasks('plugins.installed.webhooks_ui.tasks')

        # Core's dispatcher is the only trigger (after commit, honours '*');
        # this app takes each delivery so the merchant keeps the log and replay.
        self.register_hook(events.WEBHOOK_DELIVER, _take_delivery, priority=50)

    def on_dashboard_search(self, value, query='', words=None, **kwargs):
        """Webhook endpoints (by name or address) in the dashboard's search box."""
        from core.models import WebhookEndpoint
        from plugins import dashboard_search as ds

        return ds.add(
            value,
            WebhookEndpoint,
            query,
            words,
            fields=('name', 'url'),
            section='Webhooks',
            kind='webhook',
            icon='webhook',
            capability='system.write',
            label=lambda w: w.name or w.url,
            hint=lambda w: w.url,
            url=lambda w: f'/dashboard/webhooks/{w.pk}/edit/',
        )

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Webhooks',
                slug='endpoints',
                view='plugins.installed.webhooks_ui.views.endpoints_list',
                icon='webhook',
                section='developer',
                order=10,
                nav='settings',
                hint='Endpoints that receive store events',
            ),
            DashboardPage(
                label='Deliveries',
                slug='deliveries',
                view='plugins.installed.webhooks_ui.views.deliveries_list',
                icon='list',
                section='developer',
                order=20,
                nav='settings',
                hint='Every webhook sent, with its response',
            ),
        ]

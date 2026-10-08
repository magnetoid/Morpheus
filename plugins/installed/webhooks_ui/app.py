"""Webhooks UI plugin manifest."""

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin
from morpheus.core import events

logger = logging.getLogger('morpheus.webhooks_ui')

# Events the fan-out subscribes to. Merchants opt in per-endpoint by
# listing these strings in `WebhookEndpoint.events`; events not in this
# tuple won't fan out automatically (plugins can still call
# enqueue_delivery directly for custom events).
_FANOUT_EVENTS = (
    events.ORDER_PLACED,
    events.ORDER_CONFIRMED,
    events.ORDER_PAID,
    events.ORDER_CANCELLED,
    events.ORDER_FULFILLED,
    events.PAYMENT_CAPTURED,
    events.PAYMENT_REFUNDED,
    events.CUSTOMER_REGISTERED,
    events.PRODUCT_CREATED,
    events.PRODUCT_UPDATED,
    events.PRODUCT_LOW_STOCK,
    events.PRODUCT_OUT_OF_STOCK,
)


def _flatten(value):
    """Best-effort serializable representation of a domain object.

    For Django model instances we surface a few common identifying fields
    (pk, str, plus order_number / sku / email if present). Subscribers
    expect external IDs, not full record dumps.
    """
    if value is None or isinstance(value, (str, int, float, bool, list, dict)):
        return value
    out = {'_type': type(value).__name__}
    pk = getattr(value, 'pk', None)
    if pk is not None:
        out['id'] = str(pk)
    for attr in ('order_number', 'sku', 'email', 'name', 'slug', 'status'):
        v = getattr(value, attr, None)
        if v is not None and isinstance(v, (str, int, float, bool)):
            out[attr] = v
    return out


def _make_fanout(event_name: str):
    """Build a named handler closure — hook registry needs `__qualname__`."""

    def handler(**payload):
        WebhooksUiPlugin._fanout(event_name, **payload)

    safe = event_name.replace('.', '_')
    handler.__name__ = f'fanout_{safe}'
    handler.__qualname__ = f'WebhooksUiPlugin.fanout_{safe}'
    return handler


class WebhooksUiPlugin(Plugin):
    name = 'webhooks_ui'
    label = 'Webhooks'
    version = '1.0.0'
    description = (
        'Merchant-facing CRUD for WebhookEndpoint + a delivery log with '
        'retry/replay for failed deliveries. Adds a celery task that signs '
        'and POSTs payloads with HMAC-SHA256. Subscribes to core domain '
        'events and fans them out to merchant-registered endpoints.'
    )
    has_models = True

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.webhooks_ui.urls',
            prefix='dashboard/webhooks/',
            namespace='webhooks_ui',
        )
        self.register_celery_tasks('plugins.installed.webhooks_ui.tasks')

        # Subscribe a fan-out handler to every event in _FANOUT_EVENTS.
        # `priority=90` lets domain plugins react first (inventory commit,
        # invoice generation, etc.) before we serialize and ship.
        for event in _FANOUT_EVENTS:
            self.register_hook(event, _make_fanout(event), priority=90)

    @staticmethod
    def _fanout(event_name: str, **payload) -> None:
        """Find every WebhookEndpoint subscribed to `event_name` and queue.

        Previously this method was accidentally nested inside _make_fanout
        (wrong indentation) — every fanout call raised AttributeError. The
        method is now a real classmember on the plugin.
        """
        try:
            from core.models import WebhookEndpoint
            from plugins.installed.webhooks_ui.services import enqueue_delivery
        except Exception as e:  # noqa: BLE001 — DB / migrations may be late
            logger.debug('webhooks_ui fanout import failed: %s', e)
            return
        try:
            # Force evaluation inside the try: the events__contains lookup is
            # lazy, so iterating it later (outside this guard) would propagate
            # backend errors — e.g. sqlite has no JSON contains, which would
            # otherwise break the model write that fired this event.
            endpoints = list(
                WebhookEndpoint.objects.filter(
                    is_active=True,
                    events__contains=[event_name],
                )
            )
        except Exception as e:  # noqa: BLE001
            logger.debug('webhooks_ui fanout query failed: %s', e)
            return
        # Domain objects aren't JSON-serializable; flatten what we can.
        flat = {k: _flatten(v) for k, v in payload.items()}
        for ep in endpoints:
            try:
                enqueue_delivery(endpoint=ep, event_name=event_name, payload=flat)
            except Exception as e:  # noqa: BLE001
                logger.warning('webhooks_ui: enqueue %s for %s failed: %s', event_name, ep.id, e)

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

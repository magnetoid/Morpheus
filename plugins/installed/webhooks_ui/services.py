"""Webhook delivery service."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

logger = logging.getLogger('morpheus.webhooks_ui')


def enqueue_delivery(*, endpoint, event_name: str, payload: dict):
    """Create a WebhookDelivery row and queue the celery task."""
    from plugins.installed.webhooks_ui.models import WebhookDelivery

    d = WebhookDelivery.objects.create(
        endpoint=endpoint,
        event_name=event_name,
        payload=payload,
        status='queued',
    )
    try:
        from plugins.installed.webhooks_ui.tasks import deliver_webhook

        deliver_webhook.delay(str(d.id))
    except Exception as e:  # noqa: BLE001
        logger.warning('webhooks_ui: enqueue failed: %s', e)
    return d


def sign_payload(secret: str, body: bytes) -> str:
    """Same scheme used by core.tasks.compute_hmac_signature."""
    return 'sha256=' + hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()


def build_signed_request_body(*, event_name: str, payload: dict) -> bytes:
    return json.dumps({'event': event_name, 'data': payload}, default=str, sort_keys=True).encode(
        'utf-8'
    )

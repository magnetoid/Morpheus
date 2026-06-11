"""Webhook delivery celery task with exponential-backoff retries + DLQ."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

from morph.celery import app

logger = logging.getLogger('morpheus.webhooks_ui')


# Backoff schedule per attempt (seconds). Attempt 7 = DLQ.
_BACKOFF_SECONDS = (1, 2, 4, 8, 16, 30)
_MAX_ATTEMPTS = len(_BACKOFF_SECONDS) + 1  # 7 — last attempt before DLQ


@app.task(name='webhooks_ui.deliver', acks_late=True, time_limit=20, soft_time_limit=10)
def deliver_webhook(delivery_id: str) -> None:
    """Single delivery attempt. Schedules itself again on transient failure;
    moves to status='dlq' after _MAX_ATTEMPTS."""
    from plugins.installed.webhooks_ui.models import WebhookDelivery
    from plugins.installed.webhooks_ui.services import (
        build_signed_request_body,
        sign_payload,
    )

    try:
        d = WebhookDelivery.objects.select_related('endpoint').get(id=delivery_id)
    except WebhookDelivery.DoesNotExist:
        return
    if not d.endpoint.is_active:
        d.status = 'failed'
        d.error_message = 'endpoint inactive'
        d.save(update_fields=['status', 'error_message'])
        return

    d.status = 'delivering'
    d.attempts = (d.attempts or 0) + 1
    d.save(update_fields=['status', 'attempts'])

    body = build_signed_request_body(event_name=d.event_name, payload=d.payload)
    headers = {
        'Content-Type': 'application/json',
        'X-Morpheus-Event': d.event_name,
        'X-Morpheus-Signature': sign_payload(d.endpoint.secret or '', body),
        'X-Morpheus-Delivery': str(d.id),
        'X-Morpheus-Attempt': str(d.attempts),
    }

    success = False
    try:
        import requests

        resp = requests.post(d.endpoint.url, data=body, headers=headers, timeout=10)
        d.response_status = resp.status_code
        d.response_body = (resp.text or '')[:5000]
        success = 200 <= resp.status_code < 300
        if not success:
            d.error_message = f'HTTP {resp.status_code}'
    except Exception as e:  # noqa: BLE001
        d.error_message = f'{type(e).__name__}: {e}'[:1000]

    if success:
        d.status = 'delivered'
        d.delivered_at = timezone.now()
        d.next_retry_at = None
        d.save(
            update_fields=[
                'status',
                'response_status',
                'response_body',
                'error_message',
                'delivered_at',
                'next_retry_at',
            ]
        )
        return

    # Failure: either schedule another attempt or DLQ.
    if d.attempts < _MAX_ATTEMPTS:
        delay = _BACKOFF_SECONDS[d.attempts - 1]
        d.status = 'retrying'
        d.next_retry_at = timezone.now() + timedelta(seconds=delay)
        d.save(
            update_fields=[
                'status',
                'response_status',
                'response_body',
                'error_message',
                'next_retry_at',
            ]
        )
        try:
            deliver_webhook.apply_async(args=[str(d.id)], countdown=delay)
        except Exception as e:  # noqa: BLE001
            logger.warning('webhooks_ui: retry schedule failed: %s', e)
    else:
        d.status = 'dlq'
        d.next_retry_at = None
        d.save(
            update_fields=[
                'status',
                'response_status',
                'response_body',
                'error_message',
                'next_retry_at',
            ]
        )
        logger.warning(
            'webhooks_ui: %s delivery %s moved to DLQ after %d attempts',
            d.event_name,
            d.id,
            d.attempts,
        )


@app.task(name='webhooks_ui.replay')
def replay_delivery(delivery_id: str) -> None:
    """Reset a failed/DLQ delivery and re-enqueue. Triggered by the
    'Replay' button in the delivery log UI."""
    from plugins.installed.webhooks_ui.models import WebhookDelivery

    try:
        d = WebhookDelivery.objects.get(id=delivery_id)
    except WebhookDelivery.DoesNotExist:
        return
    d.attempts = 0
    d.status = 'queued'
    d.error_message = ''
    d.response_status = None
    d.response_body = ''
    d.delivered_at = None
    d.next_retry_at = None
    d.save()
    deliver_webhook.delay(str(d.id))

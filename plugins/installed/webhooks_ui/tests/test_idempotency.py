"""Webhook delivery is idempotent under broker redelivery (enterprise audit).

`deliver_webhook` runs with acks_late=True: a worker crash/timeout AFTER the
POST but before the ack makes the broker redeliver the task. Without the
delivered-guard the same delivery re-POSTs — duplicate downstream side effects
(double emails, double order events). Replay still works because it resets
status to 'queued' first.
"""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from core.models import WebhookEndpoint
from plugins.installed.webhooks_ui.models import WebhookDelivery
from plugins.installed.webhooks_ui.tasks import deliver_webhook


class DeliveryIdempotencyTests(TestCase):
    def setUp(self):
        self.endpoint = WebhookEndpoint.objects.create(
            name='test', url='https://example.test/hook', is_active=True
        )

    def _delivery(self, **kw):
        return WebhookDelivery.objects.create(
            endpoint=self.endpoint, event_name='order.placed', payload={'id': 1}, **kw
        )

    def test_redelivery_of_delivered_row_does_not_repost(self):
        d = self._delivery(status='delivered', delivered_at=timezone.now(), attempts=1)
        with patch('requests.post') as post:
            deliver_webhook(str(d.id))
            post.assert_not_called()
        d.refresh_from_db()
        self.assertEqual(d.status, 'delivered')
        self.assertEqual(d.attempts, 1)  # unchanged — no second attempt recorded

    def test_queued_delivery_posts_once_and_marks_delivered(self):
        d = self._delivery(status='queued')
        with patch('requests.post') as post:
            post.return_value.status_code = 200
            post.return_value.text = 'ok'
            deliver_webhook(str(d.id))
            self.assertEqual(post.call_count, 1)
        d.refresh_from_db()
        self.assertEqual(d.status, 'delivered')
        # …and a broker redelivery of the SAME task is now a no-op.
        with patch('requests.post') as post2:
            deliver_webhook(str(d.id))
            post2.assert_not_called()

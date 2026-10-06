"""The deep health probe's outbox check must count something.

``/healthz/deep`` reported the outbox as ok with ``"unavailable"`` on every
store from the day it shipped: it filtered ``OutboxEvent`` on ``sent_at``, a
field the model has never had, and the resulting ``FieldError`` was swallowed
by the fail-soft ``except``. A check that reports ok while its own query is
broken is not a check.
"""

from __future__ import annotations

from django.test import TestCase

from core.models import OutboxEvent


class DeepHealthOutboxTests(TestCase):
    def test_outbox_check_counts_pending_rows(self):
        OutboxEvent.objects.create(event_type='order.placed', payload={})
        OutboxEvent.objects.create(event_type='order.paid', payload={}, status='PUBLISHED')

        outbox = self.client.get('/healthz/deep').json()['checks']['outbox']

        self.assertNotIn('note', outbox, outbox)
        self.assertEqual(outbox['unsent'], 1)
        self.assertTrue(outbox['ok'])

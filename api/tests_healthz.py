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


class DeepHealthRedactionTests(TestCase):
    """The deep probe is public (uptime monitors poll it), so a failing check
    must not hand an anonymous caller the exception text — a provider error can
    name a key or a host. Staff still see it."""

    def _degraded(self):
        from unittest.mock import patch

        with patch(
            'core.assistant.providers.get_default_provider',
            side_effect=RuntimeError('provider key xyz-secret invalid'),
        ):
            return self.client.get('/healthz/deep')

    def test_anonymous_sees_the_failure_without_the_text(self):
        r = self._degraded()
        self.assertEqual(r.status_code, 503)
        self.assertFalse(r.json()['checks']['assistant']['ok'])
        self.assertNotIn('xyz-secret', r.content.decode())

    def test_staff_sees_the_text(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username='hz', email='hz@x.test', password='pw', is_staff=True
        )
        self.client.force_login(user)
        r = self._degraded()
        self.assertIn('xyz-secret', r.json()['checks']['assistant']['error'])

"""Transactional-outbox publish: bounded retry + dead-letter (enterprise-readiness).

Before this, a failed NATS publish set status='FAILED' permanently — a transient
network blip stranded the event forever. Now a failure keeps the row PENDING
(retried on the next drain) and increments `attempts`, dead-lettering to FAILED
only after `_OUTBOX_MAX_ATTEMPTS`. Also guards the fix for `process_outbox`
never being scheduled on the Celery beat (morph/celery.py) — see the audit
docs/plans/enterprise-readiness-2026-07.md.

Tests target `_process_outbox_event` directly: the per-event logic was extracted
so it's testable without the `FOR UPDATE SKIP LOCKED` drain query, which sqlite
(the test DB) cannot execute.
"""

from __future__ import annotations

import os
from unittest.mock import patch

from django.test import TestCase

from core.models import OutboxEvent
from core.tasks import _OUTBOX_MAX_ATTEMPTS, _process_outbox_event, process_outbox


class OutboxRetryTests(TestCase):
    def _event(self):
        return OutboxEvent.objects.create(event_type='order.placed', payload={'id': 1})

    def test_success_marks_published(self):
        e = self._event()
        with patch('core.tasks._publish_to_nats_sync') as pub:
            _process_outbox_event(e)
            pub.assert_called_once_with('order.placed', {'id': 1})
        e.refresh_from_db()
        self.assertEqual(e.status, 'PUBLISHED')
        self.assertIsNotNone(e.published_at)
        self.assertEqual(e.attempts, 0)

    def test_transient_failure_stays_pending_for_retry(self):
        e = self._event()
        with patch('core.tasks._publish_to_nats_sync', side_effect=RuntimeError('nats down')):
            _process_outbox_event(e)
        e.refresh_from_db()
        self.assertEqual(e.status, 'PENDING')  # NOT permanently FAILED
        self.assertEqual(e.attempts, 1)
        self.assertIn('nats down', e.error_message)

    def test_dead_letters_after_max_attempts(self):
        e = self._event()
        with patch('core.tasks._publish_to_nats_sync', side_effect=RuntimeError('nats down')):
            for _ in range(_OUTBOX_MAX_ATTEMPTS):
                _process_outbox_event(e)
        e.refresh_from_db()
        self.assertEqual(e.attempts, _OUTBOX_MAX_ATTEMPTS)
        self.assertEqual(e.status, 'FAILED')

    def test_retry_then_success_publishes(self):
        e = self._event()
        with patch('core.tasks._publish_to_nats_sync', side_effect=RuntimeError('nats down')):
            _process_outbox_event(e)
        self.assertEqual(OutboxEvent.objects.get(pk=e.pk).status, 'PENDING')
        with patch('core.tasks._publish_to_nats_sync'):
            _process_outbox_event(e)  # next drain succeeds
        e.refresh_from_db()
        self.assertEqual(e.status, 'PUBLISHED')
        self.assertEqual(e.attempts, 1)  # attempt count preserved from the failed try

    def test_drain_skips_when_nats_unconfigured(self):
        # Prod ships without NATS (NATS_URL unset) — the beat drain must no-op
        # quietly and leave events PENDING, NOT connect/fail/dead-letter them.
        e = self._event()
        env = {k: v for k, v in os.environ.items() if k != 'NATS_URL'}
        with (
            patch.dict(os.environ, env, clear=True),
            patch('core.tasks._publish_to_nats_sync') as pub,
        ):
            process_outbox.apply()  # runs the task body synchronously
            pub.assert_not_called()  # never even attempted a publish
        e.refresh_from_db()
        self.assertEqual(e.status, 'PENDING')
        self.assertEqual(e.attempts, 0)


class OutboxDrainLockTests(TestCase):
    """The drain locked its batch in one transaction and published after it had
    ended, so two drains running together both published every row."""

    def test_a_row_another_drain_published_meanwhile_is_not_published_again(self):
        first = OutboxEvent.objects.create(event_type='order.placed', payload={'id': 1})
        second = OutboxEvent.objects.create(event_type='order.placed', payload={'id': 2})
        sent = []

        def publish(event_type, payload):
            sent.append(payload['id'])
            # Another worker's drain finishes the second row while this one is
            # still publishing the first.
            OutboxEvent.objects.filter(pk=second.pk).update(status='PUBLISHED')

        with (
            patch.dict(os.environ, {'NATS_URL': 'nats://nats.invalid:4222'}),
            patch('core.tasks._publish_to_nats_sync', side_effect=publish),
        ):
            process_outbox()

        self.assertEqual(sent, [1])
        first.refresh_from_db()
        self.assertEqual(first.status, 'PUBLISHED')

    def test_every_pending_row_is_published_once(self):
        for n in (1, 2, 3):
            OutboxEvent.objects.create(event_type='order.placed', payload={'id': n})
        with (
            patch.dict(os.environ, {'NATS_URL': 'nats://nats.invalid:4222'}),
            patch('core.tasks._publish_to_nats_sync') as pub,
        ):
            process_outbox()
        self.assertEqual(pub.call_count, 3)
        self.assertFalse(OutboxEvent.objects.filter(status='PENDING').exists())

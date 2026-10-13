"""What the error log keeps, and what it must never keep (2026-10-13 review).

A review of 30 days on four stores found: a message quoting a provider key would
have been stored and emailed as it was (only emails, phones and IPs were hashed);
113 of 141 groups still "open" weeks after their last event, so the list never
showed what is broken now; and a Janus turn that gave the merchant no reply was
logged as a WARNING, which the log keeps only while detailed capture is on.
"""

from __future__ import annotations

import logging
import subprocess
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from core.errors.models import ErrorEvent, ErrorGroup
from core.errors.services import is_client_noise, record_error, record_message

SECRETS = (
    'sk-proj-AbCdEf0123456789abcdef0123456789',
    'Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature123',
    'lt1.eyJ1IjoxfQ.c2lnbmF0dXJlLWhlcmU',
    'ghp_0123456789abcdefABCDEF0123456789abcd',
    'AKIAIOSFODNN7EXAMPLE',
)


class SecretRedactionTests(TestCase):
    def test_a_message_never_stores_a_key_or_token(self):
        for secret in SECRETS:
            record_message(f'Provider said: invalid credentials {secret} (401)', source='test')
        stored = ' '.join(ErrorEvent.objects.values_list('message', flat=True))
        for secret in SECRETS:
            self.assertNotIn(secret, stored)
        self.assertIn('invalid credentials', stored)

    def test_an_exception_and_its_traceback_never_store_a_key(self):
        try:
            raise RuntimeError('Incorrect API key provided: sk-live-ZZZZabcdefghijklmnopqrstuv')
        except RuntimeError as e:
            record_error(e, kind='server')
        event = ErrorEvent.objects.get()
        self.assertNotIn('sk-live-ZZZZabcdefghijklmnopqrstuv', event.message + event.traceback)

    def test_a_password_in_a_url_or_setting_is_removed(self):
        record_message(
            'connect failed: postgres://morpheus:hunter2secret@db:5432/x api_key=abc123def456',
            source='test',
        )
        msg = ErrorEvent.objects.get().message
        self.assertNotIn('hunter2secret', msg)
        self.assertNotIn('abc123def456', msg)


class BrowserNoiseTests(SimpleTestCase):
    def test_every_aborted_page_transition_is_noise(self):
        self.assertTrue(is_client_noise('AbortError', 'Transition was skipped'))
        self.assertTrue(
            is_client_noise('InvalidStateError', 'Transition was aborted because of invalid state.')
        )

    def test_an_opaque_cross_origin_error_is_noise(self):
        # The browser hides everything about it: no message, file or line to act on.
        self.assertTrue(is_client_noise('Error', 'Script error.'))

    def test_a_real_error_is_not_noise(self):
        self.assertFalse(is_client_noise('TypeError', 'x is undefined'))


class StaleGroupTests(TestCase):
    def _event(self, fp, days_ago):
        e = ErrorEvent.objects.create(kind='server', fingerprint=fp, message='m')
        ErrorEvent.objects.filter(pk=e.pk).update(
            created_at=timezone.now() - timedelta(days=days_ago)
        )

    def test_a_group_quiet_for_two_weeks_is_resolved_and_a_recent_one_stays_open(self):
        from core.errors.report import resolve_stale, status_of

        self._event('old', 20)
        self._event('new', 2)
        self.assertEqual(resolve_stale(days=14), 1)
        self.assertEqual(ErrorGroup.objects.get(fingerprint='old').status, 'resolved')
        self.assertFalse(ErrorGroup.objects.filter(fingerprint='new', status='resolved').exists())
        # It comes back: the list shows it as regressed, not as quietly resolved.
        self._event('old', 0)
        last = ErrorEvent.objects.filter(fingerprint='old').latest('created_at').created_at
        self.assertEqual(status_of(ErrorGroup.objects.get(fingerprint='old'), last), 'regressed')

    def test_the_nightly_prune_resolves_stale_groups(self):
        from core.errors.tasks import prune_errors_task

        self._event('old', 20)
        prune_errors_task()
        self.assertEqual(ErrorGroup.objects.get(fingerprint='old').status, 'resolved')


class JanusFailureLevelTests(SimpleTestCase):
    def test_a_turn_that_gives_no_reply_is_logged_as_an_error(self):
        import core.assistant.janus_engine as eng

        with (
            TemporaryDirectory() as tmp,
            mock.patch.object(eng, 'janus_cmd', return_value=['/bin/true']),
            mock.patch.object(eng, 'linda_janus_home', return_value=Path(tmp)),
            mock.patch.object(
                eng.subprocess,
                'run',
                side_effect=subprocess.TimeoutExpired(cmd='janus', timeout=55),
            ),
            self.assertLogs('morpheus.assistant.janus', level=logging.ERROR) as logs,
        ):
            eng.run_janus_turn(message='hi', conversation_key='t', system_prompt='p')
        self.assertTrue(any('timed out' in line for line in logs.output))

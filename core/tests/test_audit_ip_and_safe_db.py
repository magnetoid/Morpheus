"""An audit row survives a junk address, and a swallowed database error stays contained.

Postgres refuses text that is not an address in an inet column, so an attacker
guessing second-factor codes with ``X-Forwarded-For: x`` lost every audit row of
their attempts (sqlite stores the text, so no test saw it). And ``@safe_db``
swallowed the DatabaseError without a savepoint, which on Postgres leaves the
caller's transaction aborted (CLAUDE.md, "a fail-soft except").
"""

from __future__ import annotations

from django.db import DatabaseError, connection, transaction
from django.test import TestCase

from core.audit.models import AuditEvent
from core.audit.services import record
from core.utils.safe_db import safe_db


class AuditAddressTests(TestCase):
    def test_a_junk_address_is_dropped_and_the_row_kept(self):
        event = record(event_type='auth.mfa_failed', ip_address='x')
        self.assertIsNotNone(event)
        self.assertIsNone(AuditEvent.objects.get(pk=event.pk).ip_address)

    def test_a_real_address_is_kept(self):
        for ip in ('203.0.113.9', '2001:db8::1'):
            event = record(event_type='auth.mfa_failed', ip_address=ip)
            self.assertEqual(AuditEvent.objects.get(pk=event.pk).ip_address, ip)


class SafeDbSavepointTests(TestCase):
    def test_a_failure_rolls_back_to_its_own_savepoint_only(self):
        @safe_db(default='fallback')
        def write_then_fail():
            AuditEvent.objects.create(event_type='inner')
            raise DatabaseError('boom')

        with transaction.atomic():
            AuditEvent.objects.create(event_type='outer')
            depth = len(connection.savepoint_ids)
            self.assertEqual(write_then_fail(), 'fallback')
            self.assertEqual(len(connection.savepoint_ids), depth)
            names = set(AuditEvent.objects.values_list('event_type', flat=True))
        self.assertEqual(names, {'outer'})

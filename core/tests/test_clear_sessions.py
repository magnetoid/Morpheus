"""Expired sessions are cleared daily (nothing ever ran clearsessions)."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.test import TestCase
from django.utils import timezone

from core.tasks import clear_expired_sessions


class ClearExpiredSessionsTests(TestCase):
    def test_expired_rows_go_and_live_ones_stay(self):
        live = SessionStore()
        live.create()
        old = SessionStore()
        old.create()
        Session.objects.filter(session_key=old.session_key).update(
            expire_date=timezone.now() - timedelta(days=1)
        )
        clear_expired_sessions()
        self.assertEqual(
            list(Session.objects.values_list('session_key', flat=True)), [live.session_key]
        )

    def test_it_is_registered_under_its_name(self):
        self.assertEqual(clear_expired_sessions.name, 'core.tasks.clear_expired_sessions')

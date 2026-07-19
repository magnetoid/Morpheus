"""Auto-heal failure backoff (hunt #18).

The OPEN-status dedup lets a 'failed' recommendation re-propose next run
(failed ∉ OPEN_RECOMMENDATION_STATUSES), so a chronically-broken healer would
mint a fresh rec every nightly run forever. `_process_cluster` now stands a
fingerprint down after FAILURE_BACKOFF_LIMIT failures inside the window.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from core.self_improvement.models import SiRecommendation
from core.self_improvement.recommend import (
    FAILURE_BACKOFF_LIMIT,
    Cluster,
    _process_cluster,
)
from core.self_improvement.services import fingerprint_for


class AutoHealBackoffTests(TestCase):
    def _cluster(self, class_name='dead_link', fp='u/missing') -> Cluster:
        return Cluster(
            class_name=class_name,
            fingerprint=fp,
            severity=60,
            seen_count=3,
            age_hours=1.0,
            signal_ids=[],
            payload_samples=[],
        )

    def _failed_rec(self, class_name, rec_fp, *, days_ago=0):
        rec = SiRecommendation.objects.create(
            class_name=class_name,
            fingerprint=rec_fp,
            title='x',
            confidence=Decimal('0.5'),
            proposed_action={'kind': 'advise'},
            status='failed',
        )
        if days_ago:
            SiRecommendation.objects.filter(pk=rec.pk).update(
                created_at=timezone.now() - timedelta(days=days_ago)
            )
        return rec

    def test_stands_down_after_backoff_limit(self):
        c = self._cluster()
        rec_fp = fingerprint_for(c.class_name, c.fingerprint)
        for _ in range(FAILURE_BACKOFF_LIMIT):
            self._failed_rec(c.class_name, rec_fp)
        before = SiRecommendation.objects.count()
        # Backoff short-circuits BEFORE _plan (no LLM). If it didn't, patching
        # _plan proves the gate: it must NOT be reached.
        with mock.patch('core.self_improvement.recommend._plan') as m:
            out = _process_cluster(c)
        self.assertIsNone(out)
        self.assertFalse(m.called)  # stood down before planning
        self.assertEqual(SiRecommendation.objects.count(), before)

    def test_failures_outside_window_do_not_trigger_backoff(self):
        c = self._cluster(fp='u/other')
        rec_fp = fingerprint_for(c.class_name, c.fingerprint)
        # All failures older than the cooldown window → recent count is 0.
        for _ in range(FAILURE_BACKOFF_LIMIT + 1):
            self._failed_rec(c.class_name, rec_fp, days_ago=30)
        # Proceeds past the backoff gate into _plan (patched to a no-op) — the
        # point is it does NOT short-circuit at backoff.
        with mock.patch('core.self_improvement.recommend._plan', return_value=None) as m:
            _process_cluster(c)
        self.assertTrue(m.called)  # reached _plan → backoff did NOT stand it down

"""Reject/snooze suppression alignment (July 2026 audit).

Regression: reject() wrote SiSuppression rows keyed on
(rec.class_name, signal_pk) while services.emit_signal filters on
(collector source, fingerprint hash) — both axes mismatched, so a rejected
recommendation's signal re-emitted forever ("reject didn't stick"). The
dashboard now resolves the recommendation's evidence signals and suppresses
their actual (source, fingerprint), which emit_signal honours.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from core.self_improvement.models import SiRecommendation, SiSignal, SiSuppression
from core.self_improvement.services import emit_signal
from plugins.installed.admin_dashboard.views_split.self_improvement import (
    _suppress_recommendation,
)


class RejectSuppressionAlignmentTests(TestCase):
    def _recommendation_for_signal(self, sig):
        return SiRecommendation.objects.create(
            class_name='error_cluster',  # class != source ('error_log') on purpose
            title='Fix the recurring 500',
            rationale='',
            confidence=Decimal('0.90'),
            impact_score=100,
            evidence_signal_ids=[sig.pk],
            status='proposed',
        )

    def test_reject_suppresses_the_signal_that_re_emits(self) -> None:
        sig = SiSignal.objects.create(
            source='error_log', fingerprint='deadbeef', severity=80, occurred_at=timezone.now()
        )
        rec = self._recommendation_for_signal(sig)

        suppression = _suppress_recommendation(rec, reason='noise', created_by=None)

        # Keyed on the COLLECTOR's (source, fingerprint) — what emit_signal checks.
        self.assertIsNotNone(suppression)
        self.assertEqual(suppression.match_class, 'error_log')
        self.assertEqual(suppression.match_fingerprint, 'deadbeef')

        # The whole point: the same signal now gets dropped on re-emit.
        self.assertIsNone(emit_signal(source='error_log', fingerprint='deadbeef', severity=80))

    def test_no_evidence_signals_creates_no_suppression(self) -> None:
        rec = SiRecommendation.objects.create(
            class_name='error_cluster',
            title='orphan',
            rationale='',
            confidence=Decimal('0.5'),
            impact_score=1,
            evidence_signal_ids=[],
            status='proposed',
        )
        self.assertIsNone(_suppress_recommendation(rec, reason='x', created_by=None))
        self.assertEqual(SiSuppression.objects.count(), 0)

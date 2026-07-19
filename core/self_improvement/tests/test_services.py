"""Tests for core/self_improvement/services.py — the write-side contract.

What's verified:
  - emit_signal() creates a SiSignal on first call.
  - Identical (source, fingerprint) within DEDUP_WINDOW_HOURS bumps
    seen_count + max-severity, doesn't create a second row.
  - Different fingerprints create separate rows.
  - SiSuppression matching swallows the signal silently.
  - fingerprint_for() is deterministic + position-sensitive.
  - start_ingest_job + finish_ingest_job round-trip cleanly.

Project convention: Django TestCase (matches plugins/installed/orders/tests/).
"""

from __future__ import annotations

from datetime import timedelta

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from core.self_improvement.models import SiCustomization, SiSignal, SiSuppression
from core.self_improvement.services import (
    DEDUP_WINDOW_HOURS,
    emit_signal,
    fingerprint_for,
    finish_ingest_job,
    is_path_customized,
    start_ingest_job,
)


class EmitSignalTests(TestCase):
    def test_creates_row_on_first_call(self) -> None:
        row = emit_signal(
            source='error_log',
            fingerprint='abc123',
            severity=70,
            payload={'msg': 'boom'},
        )
        self.assertIsNotNone(row)
        self.assertIsNotNone(row.pk)
        self.assertEqual(row.seen_count, 1)
        self.assertEqual(row.severity, 70)
        self.assertEqual(row.payload, {'msg': 'boom'})
        self.assertEqual(SiSignal.objects.count(), 1)

    def test_dedupes_identical_fingerprint(self) -> None:
        emit_signal(source='error_log', fingerprint='same', severity=50)
        emit_signal(source='error_log', fingerprint='same', severity=50)
        emit_signal(source='error_log', fingerprint='same', severity=50)
        self.assertEqual(SiSignal.objects.count(), 1)
        row = SiSignal.objects.get(fingerprint='same')
        self.assertEqual(row.seen_count, 3)

    def test_dedup_bumps_max_severity(self) -> None:
        emit_signal(source='error_log', fingerprint='sev', severity=30)
        emit_signal(source='error_log', fingerprint='sev', severity=80)
        emit_signal(source='error_log', fingerprint='sev', severity=20)
        row = SiSignal.objects.get(fingerprint='sev')
        self.assertEqual(row.severity, 80)

    def test_dedup_merges_payload_non_destructively(self) -> None:
        emit_signal(
            source='error_log',
            fingerprint='pl',
            payload={'a': 1, 'b': 2},
        )
        emit_signal(
            source='error_log',
            fingerprint='pl',
            payload={'b': 99, 'c': 3},
        )
        row = SiSignal.objects.get(fingerprint='pl')
        self.assertEqual(row.payload, {'a': 1, 'b': 99, 'c': 3})

    def test_different_fingerprints_create_separate_rows(self) -> None:
        emit_signal(source='error_log', fingerprint='fp1')
        emit_signal(source='error_log', fingerprint='fp2')
        emit_signal(source='error_log', fingerprint='fp3')
        self.assertEqual(SiSignal.objects.count(), 3)

    def test_different_sources_dont_collapse(self) -> None:
        emit_signal(source='error_log', fingerprint='shared')
        emit_signal(source='csp', fingerprint='shared')
        self.assertEqual(SiSignal.objects.count(), 2)

    def test_old_signal_outside_window_creates_new_row(self) -> None:
        old_ts = timezone.now() - timedelta(hours=DEDUP_WINDOW_HOURS + 1)
        SiSignal.objects.create(
            source='error_log',
            fingerprint='old',
            severity=50,
            payload={},
            occurred_at=old_ts,
        )
        emit_signal(source='error_log', fingerprint='old', severity=50)
        self.assertEqual(SiSignal.objects.filter(fingerprint='old').count(), 2)

    def test_suppression_silences_signal(self) -> None:
        SiSuppression.objects.create(
            match_class='error_log',
            match_fingerprint='spam',
            reason='dev noise',
        )
        result = emit_signal(source='error_log', fingerprint='spam', severity=80)
        self.assertIsNone(result)
        self.assertEqual(SiSignal.objects.filter(fingerprint='spam').count(), 0)

    def test_expired_suppression_does_not_silence(self) -> None:
        SiSuppression.objects.create(
            match_class='error_log',
            match_fingerprint='past',
            reason='temporary',
            expires_at=timezone.now() - timedelta(hours=1),
        )
        result = emit_signal(source='error_log', fingerprint='past', severity=50)
        self.assertIsNotNone(result)

    def test_unrelated_suppression_passes_through(self) -> None:
        SiSuppression.objects.create(
            match_class='error_log',
            match_fingerprint='other',
            reason='not this one',
        )
        result = emit_signal(source='error_log', fingerprint='different', severity=50)
        self.assertIsNotNone(result)

    def test_classwide_suppression_silences_every_fingerprint(self) -> None:
        """A blank match_fingerprint suppresses the whole source/class — the
        model documents it, and emit_signal now honours it."""
        SiSuppression.objects.create(
            match_class='error_log',
            match_fingerprint='',
            reason='mute the whole class',
        )
        self.assertIsNone(emit_signal(source='error_log', fingerprint='anything', severity=50))
        self.assertIsNone(emit_signal(source='error_log', fingerprint='else', severity=50))
        # A different source is untouched.
        self.assertIsNotNone(emit_signal(source='zero_search', fingerprint='anything', severity=50))

    def test_severity_clamped(self) -> None:
        row_lo = emit_signal(source='error_log', fingerprint='lo', severity=-5)
        row_hi = emit_signal(source='error_log', fingerprint='hi', severity=999)
        self.assertEqual(row_lo.severity, 0)
        self.assertEqual(row_hi.severity, 100)

    def test_missing_source_raises(self) -> None:
        with self.assertRaises(ValueError):
            emit_signal(source='', fingerprint='x')

    def test_missing_fingerprint_raises(self) -> None:
        with self.assertRaises(ValueError):
            emit_signal(source='error_log', fingerprint='')


class AnalyzerDedupTests(TestCase):
    """Regression (July 2026 audit): the analyzer created a fresh
    SiRecommendation for the same (class, cluster) every nightly run, so a
    suppressed-but-still-emitting signal resurrected as a new backlog row daily.
    A stable rec-level fingerprint now guards creation."""

    def _cluster(self, fingerprint='fp-abc'):
        from core.self_improvement.recommend import Cluster  # noqa: PLC0415

        return Cluster(
            class_name='test_dedup_class',  # unknown class → enabled, proposes @0.5
            fingerprint=fingerprint,
            severity=70,
            seen_count=5,
            age_hours=1.0,
            signal_ids=[1],
            payload_samples=[{}],
        )

    def test_same_cluster_is_not_reproposed(self) -> None:
        from unittest.mock import patch  # noqa: PLC0415

        from core.self_improvement.models import SiRecommendation  # noqa: PLC0415
        from core.self_improvement.recommend import _process_cluster  # noqa: PLC0415

        cluster = self._cluster()
        # No LLM in tests → heuristic plan (confidence 0.5) + fail-open verify.
        with patch('core.assistant.providers.get_default_provider', return_value=None):
            first = _process_cluster(cluster)
            self.assertIsNotNone(first)
            self.assertEqual(first.fingerprint, fingerprint_for('test_dedup_class', 'fp-abc'))
            # Second pass over the identical cluster is deduped.
            self.assertIsNone(_process_cluster(cluster))
        self.assertEqual(SiRecommendation.objects.filter(class_name='test_dedup_class').count(), 1)

    def test_distinct_fingerprint_still_creates(self) -> None:
        from unittest.mock import patch  # noqa: PLC0415

        from core.self_improvement.models import SiRecommendation  # noqa: PLC0415
        from core.self_improvement.recommend import _process_cluster  # noqa: PLC0415

        with patch('core.assistant.providers.get_default_provider', return_value=None):
            self.assertIsNotNone(_process_cluster(self._cluster('fp-one')))
            self.assertIsNotNone(_process_cluster(self._cluster('fp-two')))
        self.assertEqual(SiRecommendation.objects.filter(class_name='test_dedup_class').count(), 2)


class FingerprintForTests(TestCase):
    def test_deterministic(self) -> None:
        self.assertEqual(fingerprint_for('a', 'b', 'c'), fingerprint_for('a', 'b', 'c'))

    def test_position_sensitive(self) -> None:
        self.assertNotEqual(fingerprint_for('a', 'b'), fingerprint_for('b', 'a'))

    def test_none_treated_as_empty(self) -> None:
        self.assertEqual(
            fingerprint_for('a', None, 'c'),
            fingerprint_for('a', '', 'c'),
        )

    def test_returns_hex_string(self) -> None:
        fp = fingerprint_for('source', 'rule', 'path')
        self.assertEqual(len(fp), 32)
        self.assertTrue(all(c in '0123456789abcdef' for c in fp))


class IngestJobLifecycleTests(TestCase):
    def test_start_creates_open_row(self) -> None:
        job = start_ingest_job('error_log')
        self.assertIsNotNone(job.pk)
        self.assertEqual(job.collector, 'error_log')
        self.assertEqual(job.status, 'ok')
        self.assertIsNone(job.finished_at)
        self.assertEqual(job.signals_emitted, 0)

    def test_finish_stamps_status_and_count(self) -> None:
        job = start_ingest_job('seo_gap')
        finish_ingest_job(job, signals_emitted=42, status='ok')
        job.refresh_from_db()
        self.assertIsNotNone(job.finished_at)
        self.assertEqual(job.signals_emitted, 42)
        self.assertEqual(job.status, 'ok')

    def test_finish_with_failure(self) -> None:
        job = start_ingest_job('code_quality')
        finish_ingest_job(job, signals_emitted=0, status='failed', error='ruff segfault')
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertIn('ruff segfault', job.error)

    def test_finish_truncates_huge_error(self) -> None:
        job = start_ingest_job('x')
        finish_ingest_job(job, signals_emitted=0, status='failed', error='X' * 10000)
        job.refresh_from_db()
        self.assertLessEqual(len(job.error), 4096)


class IsPathCustomizedTests(TestCase):
    def test_no_row_returns_false(self) -> None:
        self.assertFalse(is_path_customized('plugins/installed/storefront/views.py'))

    def test_intentional_row_returns_true(self) -> None:
        SiCustomization.objects.create(
            path='plugins/installed/storefront/views.py',
            intent='intentional',
            why='shop-specific tweak',
        )
        self.assertTrue(is_path_customized('plugins/installed/storefront/views.py'))

    def test_vendor_specific_returns_true(self) -> None:
        SiCustomization.objects.create(
            path='themes/library/dot_books/templates/home.html',
            intent='vendor_specific',
            why='brand identity',
        )
        self.assertTrue(is_path_customized('themes/library/dot_books/templates/home.html'))

    def test_experimental_returns_false(self) -> None:
        # `experimental` is allowed through — declared as a probe.
        SiCustomization.objects.create(
            path='plugins/installed/storefront/probe.py',
            intent='experimental',
            why='trying something',
        )
        self.assertFalse(is_path_customized('plugins/installed/storefront/probe.py'))


class SiSuppressionUniqueConstraintTests(TestCase):
    def test_two_active_suppressions_for_same_target_blocked(self) -> None:
        SiSuppression.objects.create(
            match_class='error_log',
            match_fingerprint='exact',
            reason='first',
        )
        with self.assertRaises(IntegrityError):
            SiSuppression.objects.create(
                match_class='error_log',
                match_fingerprint='exact',
                reason='second — should fail',
            )

    def test_expired_suppression_does_not_block_new(self) -> None:
        SiSuppression.objects.create(
            match_class='error_log',
            match_fingerprint='reused',
            reason='first',
            expires_at=timezone.now() - timedelta(hours=1),
        )
        SiSuppression.objects.create(
            match_class='error_log',
            match_fingerprint='reused',
            reason='fresh',
        )
        self.assertEqual(SiSuppression.objects.count(), 2)

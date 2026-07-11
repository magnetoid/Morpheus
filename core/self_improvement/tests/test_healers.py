"""Phase 2 healer tests.

Each healer has:
  - propose() — pure projection, no DB writes.
  - safe_to_apply() — guard checks return (ok, why).
  - apply() — actual writes; idempotent + DB-safe.
  - verify() — post-condition check.

Plus end-to-end dispatch through heal.run_one for the orchestration
trail (gate → execute → verify) writing SiActionLog rows.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from core.self_improvement.healers.base import (
    Healer,
    HealResult,
    get_healer,
    known_classes,
    register_healer,
)


class RegistryTests(TestCase):
    def test_all_four_phase_2_healers_register(self):
        # Import the modules so their @register_healer decorators fire.
        from core.self_improvement.healers import (  # noqa: F401, PLC0415
            alt_text,
            meta_description,
            redirect,
            synonym,
        )

        classes = known_classes()
        self.assertIn('alt_text', classes)
        self.assertIn('meta_description', classes)
        self.assertIn('redirect', classes)
        self.assertIn('synonym', classes)

    def test_analyzer_classes_resolve_to_healers(self):
        # Regression (July 2026 audit): the analyzer emits PROBLEM classes
        # ('seo_gap', 'zero_search', …) while healers register CAPABILITY
        # names ('alt_text', …). get_healer(rec.class_name) never matched, so
        # every approved recommendation blocked 'no_healer' and the heal loop
        # was inert. resolve_healers() bridges the two taxonomies.
        from core.self_improvement.healers import (  # noqa: F401, PLC0415
            alt_text,
            meta_description,
            redirect,
            synonym,
        )
        from core.self_improvement.healers.base import resolve_healers  # noqa: PLC0415

        self.assertEqual(
            [h.class_name for h in resolve_healers('seo_gap')],
            ['alt_text', 'meta_description'],
        )
        self.assertEqual([h.class_name for h in resolve_healers('zero_search')], ['synonym'])
        self.assertEqual([h.class_name for h in resolve_healers('dead_link')], ['redirect'])
        # Exact capability names still resolve to themselves.
        self.assertEqual([h.class_name for h in resolve_healers('alt_text')], ['alt_text'])
        self.assertEqual(resolve_healers('upstream_sync'), [])  # no executor shipped yet

    def test_get_healer_returns_correct_subclass(self):
        from core.self_improvement.healers import alt_text  # noqa: F401, PLC0415

        h = get_healer('alt_text')
        self.assertIsNotNone(h)
        self.assertEqual(h.class_name, 'alt_text')

    def test_get_healer_unknown_returns_none(self):
        self.assertIsNone(get_healer('does_not_exist'))

    def test_register_rejects_non_healer(self):
        with self.assertRaises(TypeError):

            @register_healer('not_a_healer')
            class _NotHealer:
                pass


class MetaDescriptionSummariserTests(TestCase):
    """The Phase 2 deterministic summariser is the heart of the healer."""

    def setUp(self):
        from core.self_improvement.healers.meta_description import (  # noqa: PLC0415
            MetaDescriptionHealer,
        )

        self.summarise = MetaDescriptionHealer._summarise

    def test_short_text_passes_through(self):
        # 100 chars-ish, well under TARGET_MAX
        text = 'A clever first sentence about Peter Pan.'
        self.assertEqual(self.summarise(text, fallback=''), text)

    def test_first_sentence_preferred_when_in_range(self):
        text = (
            'Peter Pan flies through the night with the Darling children. '
            'Then they meet Captain Hook, who has it in for the boys.'
        )
        out = self.summarise(text, fallback='')
        self.assertTrue(out.endswith('.'))
        self.assertLess(len(out), 161)

    def test_hard_truncate_falls_back_to_word_boundary(self):
        text = 'word ' * 80  # 400+ chars, no sentence boundaries
        out = self.summarise(text, fallback='')
        self.assertLessEqual(len(out), 161)
        # Ends on a word boundary + ellipsis.
        self.assertTrue(out.endswith('…'))

    def test_empty_text_uses_fallback(self):
        out = self.summarise('', fallback='Some Book Title')
        self.assertEqual(out, 'Some Book Title')

    def test_empty_text_and_fallback(self):
        self.assertEqual(self.summarise('', fallback=''), '')


class RedirectNormaliserTests(TestCase):
    def setUp(self):
        from core.self_improvement.healers.redirect import RedirectHealer  # noqa: PLC0415

        self.normalise = RedirectHealer._normalise

    def test_strips_query_string(self):
        self.assertEqual(self.normalise('/products/peter-pan/?utm=x'), '/products/peter-pan/')

    def test_lowercases_slug(self):
        self.assertEqual(self.normalise('/products/Peter-Pan'), '/products/peter-pan/')

    def test_adds_trailing_slash(self):
        self.assertEqual(self.normalise('/products/foo'), '/products/foo/')

    def test_strips_fragment(self):
        self.assertEqual(self.normalise('/products/foo#section'), '/products/foo/')

    def test_empty_returns_empty(self):
        self.assertEqual(self.normalise(''), '')


class HealerProposeReturnsExpectedShape(TestCase):
    """propose() never raises and always returns the documented shape
    even when there are no evidence signals."""

    def test_alt_text_empty_recommendation(self):
        from core.self_improvement.healers.alt_text import AltTextHealer  # noqa: PLC0415

        rec = _StubRec(evidence_signal_ids=[])
        result = AltTextHealer().propose(rec)
        self.assertEqual(result['kind'], 'apply_data')
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['data_changes'], [])

    def test_meta_description_empty(self):
        from core.self_improvement.healers.meta_description import (  # noqa: PLC0415
            MetaDescriptionHealer,
        )

        rec = _StubRec(evidence_signal_ids=[])
        result = MetaDescriptionHealer().propose(rec)
        self.assertEqual(result['kind'], 'apply_data')
        self.assertEqual(result['count'], 0)

    def test_redirect_empty(self):
        from core.self_improvement.healers.redirect import RedirectHealer  # noqa: PLC0415

        rec = _StubRec(evidence_signal_ids=[])
        result = RedirectHealer().propose(rec)
        self.assertEqual(result['kind'], 'apply_data')
        self.assertEqual(result['count'], 0)

    def test_synonym_empty(self):
        from core.self_improvement.healers.synonym import SynonymHealer  # noqa: PLC0415

        rec = _StubRec(evidence_signal_ids=[])
        result = SynonymHealer().propose(rec)
        self.assertEqual(result['kind'], 'apply_data')
        self.assertEqual(result['count'], 0)


class SafeToApplyTests(TestCase):
    """The safety gate is the last line before a write — exercise it."""

    def test_customization_unsafe_blocks_all(self):
        from core.self_improvement.healers.alt_text import AltTextHealer  # noqa: PLC0415

        rec = _StubRec(evidence_signal_ids=[1, 2], is_customization_safe=False)
        ok, why = AltTextHealer().safe_to_apply(rec)
        self.assertFalse(ok)
        self.assertEqual(why, 'customization_blocks_auto_apply')

    def test_no_targets_blocks(self):
        from core.self_improvement.healers.alt_text import AltTextHealer  # noqa: PLC0415

        rec = _StubRec(evidence_signal_ids=[])  # no signals → no targets
        ok, why = AltTextHealer().safe_to_apply(rec)
        self.assertFalse(ok)
        self.assertEqual(why, 'no_target_images')


class HealResultDataclass(TestCase):
    def test_ok_default_empty_details(self):
        r = HealResult(ok=True)
        self.assertEqual(r.details, {})
        self.assertEqual(r.error, '')

    def test_failure_carries_error(self):
        r = HealResult(ok=False, error='nope')
        self.assertFalse(r.ok)
        self.assertEqual(r.error, 'nope')


class RunOneOrchestrationTests(TestCase):
    """End-to-end: run_one() drives a Healer through the phases and
    writes SiActionLog rows + updates SiRecommendation.status."""

    def setUp(self):
        from core.self_improvement.models import SiRecommendation  # noqa: PLC0415

        self.rec = SiRecommendation.objects.create(
            class_name='test_stub',
            title='Stub recommendation',
            rationale='',
            confidence=Decimal('0.95'),
            impact_score=100,
            evidence_signal_ids=[],
            proposed_action={'kind': 'apply_data'},
            status='approved',
            actor='worker',
            is_customization_safe=True,
        )

    def test_run_one_blocks_on_class_blocklist(self):
        """A class in CLASS_BLOCKLIST gets rejected at the gate."""
        from core.self_improvement.heal import run_one  # noqa: PLC0415
        from core.self_improvement.models import SiActionLog, SiRecommendation  # noqa: PLC0415

        self.rec.class_name = 'auth_logic'  # in CLASS_BLOCKLIST
        self.rec.save(update_fields=['class_name'])

        outcome = run_one(self.rec)
        self.assertEqual(outcome, 'blocked')

        rec_after = SiRecommendation.objects.get(pk=self.rec.pk)
        self.assertEqual(rec_after.status, 'failed')

        log = SiActionLog.objects.filter(recommendation=self.rec, phase='gate').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.outcome, 'blocked')
        self.assertEqual(log.details.get('reason'), 'class_blocklist')

    def test_run_one_blocks_when_no_healer_registered(self):
        from core.self_improvement.heal import run_one  # noqa: PLC0415
        from core.self_improvement.models import SiActionLog  # noqa: PLC0415

        outcome = run_one(self.rec)
        self.assertEqual(outcome, 'blocked')

        log = SiActionLog.objects.filter(recommendation=self.rec, phase='gate').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.details.get('reason'), 'no_healer')

    def test_run_one_seo_gap_arbitrates_candidates_instead_of_no_healer(self):
        # 'seo_gap' resolves to (alt_text, meta_description). With no
        # evidence both candidates refuse at their own gates, so the block
        # reason is the per-candidate map — the old outcome was a flat
        # 'no_healer' that made the whole loop inert.
        from core.self_improvement.heal import run_one  # noqa: PLC0415
        from core.self_improvement.models import SiActionLog  # noqa: PLC0415

        self.rec.class_name = 'seo_gap'
        self.rec.save(update_fields=['class_name'])

        outcome = run_one(self.rec)
        self.assertEqual(outcome, 'blocked')

        log = SiActionLog.objects.filter(recommendation=self.rec, phase='gate').first()
        self.assertIsNotNone(log)
        self.assertNotEqual(log.details.get('reason'), 'no_healer')
        self.assertIn('alt_text', log.details.get('candidates', {}))
        self.assertIn('meta_description', log.details.get('candidates', {}))

    def test_run_one_happy_path_with_stub_healer(self):
        from core.self_improvement.heal import run_one  # noqa: PLC0415
        from core.self_improvement.models import SiActionLog, SiRecommendation  # noqa: PLC0415

        @register_healer('test_stub_ok')
        class _OK(Healer):
            def propose(self, recommendation) -> dict:
                return {'kind': 'apply_data', 'count': 1}

            def safe_to_apply(self, recommendation):
                return True, ''

            def apply(self, recommendation):
                return HealResult(ok=True, details={'updated': 1})

            def verify(self, recommendation):
                return HealResult(ok=True, details={'remaining_empty': 0})

        self.rec.class_name = 'test_stub_ok'
        self.rec.save(update_fields=['class_name'])

        outcome = run_one(self.rec)
        self.assertEqual(outcome, 'ok')

        rec_after = SiRecommendation.objects.get(pk=self.rec.pk)
        # Approved → merged on happy path.
        self.assertEqual(rec_after.status, 'merged')

        phases = list(
            SiActionLog.objects.filter(recommendation=self.rec)
            .values_list('phase', 'outcome')
            .order_by('created_at')
        )
        self.assertIn(('execute', 'ok'), phases)
        self.assertIn(('verify', 'ok'), phases)

    def test_run_one_rolls_back_when_verify_fails(self):
        rollback_called = {'flag': False}

        @register_healer('test_stub_verify_fail')
        class _VerifyFails(Healer):
            def propose(self, recommendation):
                return {'kind': 'apply_data'}

            def safe_to_apply(self, recommendation):
                return True, ''

            def apply(self, recommendation):
                return HealResult(ok=True, details={'applied': 1})

            def verify(self, recommendation):
                return HealResult(ok=False, error='not converged')

            def rollback(self, recommendation):
                rollback_called['flag'] = True
                return HealResult(ok=True, details={'reverted': 1})

        from core.self_improvement.heal import run_one  # noqa: PLC0415
        from core.self_improvement.models import SiActionLog  # noqa: PLC0415

        self.rec.class_name = 'test_stub_verify_fail'
        self.rec.save(update_fields=['class_name'])

        outcome = run_one(self.rec)
        self.assertEqual(outcome, 'failed')
        self.assertTrue(rollback_called['flag'])

        rollback_logs = SiActionLog.objects.filter(recommendation=self.rec, phase='rollback')
        self.assertGreaterEqual(rollback_logs.count(), 1)


# ---------------------------------------------------------------------------


class _StubRec:
    """Minimal stand-in for SiRecommendation in pure unit tests."""

    def __init__(self, *, evidence_signal_ids=None, is_customization_safe=True):
        self.evidence_signal_ids = evidence_signal_ids or []
        self.is_customization_safe = is_customization_safe

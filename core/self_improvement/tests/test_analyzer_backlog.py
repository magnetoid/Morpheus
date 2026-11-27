"""The nightly analyzer keeps moving (v0.197.0).

Four ways it stood still or wasted the night:

- It took the 50 highest-scoring clusters first and only then skipped the ones
  that already had an open recommendation, so a store with 50 standing gaps
  never got a recommendation for anything new.
- A rejected recommendation came back the next night once its evidence signals
  were pruned (30 days): the suppression is built from those rows.
- After the provider failed once (402, a timeout) it was called again for every
  other cluster, twice each, and Celery's soft time limit was swallowed.
- ``daily_token_budget`` had no reader.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from celery.exceptions import SoftTimeLimitExceeded
from django.test import TestCase, override_settings
from django.utils import timezone

from core.self_improvement import recommend
from core.self_improvement.models import SiRecommendation, SiSignal
from core.self_improvement.services import fingerprint_for

PROVIDER = 'core.assistant.providers.get_default_provider'
PLAN_JSON = (
    '{"title": "t", "rationale": "r", "confidence": 0.6,'
    ' "proposed_action": {"kind": "advise"}, "is_customization_safe": true}'
)


def _signal(fp, *, source='seo_gap', severity=50, seen=1):
    return SiSignal.objects.create(
        source=source,
        fingerprint=fp,
        severity=severity,
        seen_count=seen,
        payload={},
        occurred_at=timezone.now(),
    )


def _rec(source_class, signal_fp, status, **extra):
    return SiRecommendation.objects.create(
        class_name=source_class,
        fingerprint=fingerprint_for(source_class, signal_fp),
        title='x',
        confidence=Decimal('0.5'),
        proposed_action={'kind': 'advise'},
        status=status,
        **extra,
    )


def _answering(text=PLAN_JSON, prompt_tokens=10, completion_tokens=5):
    provider = mock.Mock()
    provider.respond.return_value = SimpleNamespace(
        text=text, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
    )
    return provider


class CoveredBacklogTests(TestCase):
    @mock.patch(PROVIDER, return_value=None)
    @mock.patch.object(recommend, 'TOP_CLUSTERS_PER_RUN', 3)
    def test_a_covered_backlog_does_not_starve_new_signals(self, _provider):
        for n in range(5):
            _signal(f'gap-{n}', severity=90, seen=20)
            _rec('seo_gap', f'gap-{n}', 'proposed')
        _signal('fresh', source='error_log', severity=10)

        out = recommend.run_analyzer()

        self.assertEqual(out['recommendations'], 1)
        self.assertTrue(
            SiRecommendation.objects.filter(
                fingerprint=fingerprint_for('error_cluster', 'fresh')
            ).exists()
        )

    @mock.patch(PROVIDER, return_value=None)
    def test_a_rejected_recommendation_does_not_return(self, _provider):
        # Its evidence signals were pruned, so the reject wrote no suppression.
        _signal('said-no')
        _rec('seo_gap', 'said-no', 'rejected')

        out = recommend.run_analyzer()

        self.assertEqual(out['recommendations'], 0)
        self.assertEqual(SiRecommendation.objects.count(), 1)

    @mock.patch(PROVIDER, return_value=None)
    def test_a_snooze_lasts_its_thirty_days(self, _provider):
        _signal('snoozed')
        rec = _rec('seo_gap', 'snoozed', 'suppressed')
        self.assertEqual(recommend.run_analyzer()['recommendations'], 0)

        SiRecommendation.objects.filter(pk=rec.pk).update(
            updated_at=timezone.now() - timedelta(days=31)
        )
        self.assertEqual(recommend.run_analyzer()['recommendations'], 1)


class ModelUseTests(TestCase):
    def test_after_a_failed_call_the_run_stops_asking_the_model(self):
        for n in range(4):
            _signal(f'gap-{n}')
        provider = mock.Mock()
        provider.respond.side_effect = RuntimeError('402 Insufficient Balance')

        with (
            mock.patch(PROVIDER, return_value=provider),
            self.assertLogs('morpheus.self_improvement.recommend', level='ERROR'),
        ):
            out = recommend.run_analyzer()

        self.assertEqual(provider.respond.call_count, 1)
        # Every cluster still gets its plain recommendation.
        self.assertEqual(out['recommendations'], 4)

    def test_the_soft_time_limit_ends_the_run_and_reports_what_it_wrote(self):
        for n in range(4):
            _signal(f'gap-{n}')
        provider = mock.Mock()
        provider.respond.side_effect = SoftTimeLimitExceeded()

        with (
            mock.patch(PROVIDER, return_value=provider),
            mock.patch.object(recommend.hook_registry, 'fire') as fire,
        ):
            out = recommend.run_analyzer()

        self.assertEqual(provider.respond.call_count, 1)
        self.assertEqual(out['stopped'], 'time_limit')
        fire.assert_called_once_with(recommend.EVENT_BACKLOG_UPDATED, added_count=0)

    @override_settings(SELF_IMPROVEMENT={'daily_token_budget': 100})
    def test_the_daily_token_budget_ends_model_calls(self):
        for n in range(3):
            _signal(f'gap-{n}')
        provider = _answering(prompt_tokens=80, completion_tokens=40)

        with mock.patch(PROVIDER, return_value=provider):
            out = recommend.run_analyzer()

        # One planning call spends 120 of 100: no verifier call, no later plans.
        self.assertEqual(provider.respond.call_count, 1)
        self.assertEqual(out['recommendations'], 3)

    @override_settings(SELF_IMPROVEMENT={'daily_token_budget': 100})
    def test_the_budget_counts_what_today_already_spent(self):
        _signal('gap')
        _rec('seo_gap', 'earlier', 'applied', tokens_used=150)
        provider = _answering()

        with mock.patch(PROVIDER, return_value=provider):
            recommend.run_analyzer()

        provider.respond.assert_not_called()

    def test_a_working_model_plans_and_verifies_every_cluster(self):
        for n in range(2):
            _signal(f'gap-{n}')
        provider = _answering()

        with mock.patch(PROVIDER, return_value=provider):
            out = recommend.run_analyzer()

        self.assertEqual(provider.respond.call_count, 4)
        self.assertEqual(out['recommendations'], 2)
        # The verifier's tokens are on the recommendation with the planner's.
        self.assertEqual(
            list(SiRecommendation.objects.values_list('tokens_used', flat=True)), [30, 30]
        )


class NoHealerTests(TestCase):
    def test_a_class_nothing_can_heal_is_never_auto_applied(self):
        from core.self_improvement.policy import decide_action, policy_for

        self.assertGreater(policy_for('csp_drift').auto_apply_threshold, 0)
        self.assertEqual(decide_action(class_name='csp_drift', confidence=0.99), 'propose')
        # One that has a healer still is.
        self.assertEqual(decide_action(class_name='seo_gap', confidence=0.99), 'auto_apply')

    def test_zero_search_has_no_healer(self):
        # Its healer wrote to catalog.SearchSynonym, a model that never existed.
        from core.self_improvement.healers.base import resolve_healers

        self.assertEqual(resolve_healers('zero_search'), [])

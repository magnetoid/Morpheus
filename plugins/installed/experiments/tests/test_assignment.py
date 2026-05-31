"""Variant assignment + conversion tracking tests.

The core invariants the experiments plugin must preserve:
  1. Determinism — the same visitor always sees the same variant.
  2. Weight respect — over a large sample, variant distribution
     approximates configured weights.
  3. Conversion attribution — record_conversion bumps only the
     variant the visitor was originally assigned to.
  4. Lift math — results_for computes the right rates + a z-score
     that crosses 1.96 only when the sample supports it.
"""

from __future__ import annotations

import random
from decimal import Decimal

from django.test import RequestFactory, TestCase

from plugins.installed.experiments.models import (
    Assignment,
    Experiment,
    Exposure,
)
from plugins.installed.experiments.services import (
    record_conversion,
    results_for,
    variant_for,
)


class _AnonymousUser:
    is_authenticated = False
    pk = None


class _AuthUser:
    is_authenticated = True

    def __init__(self, pk):
        self.pk = pk


def _request(visitor_cookie='', user=None):
    rf = RequestFactory()
    r = rf.get('/')
    if visitor_cookie:
        r.COOKIES['morph_visitor'] = visitor_cookie
    r.user = user or _AnonymousUser()
    return r


class DeterminismTests(TestCase):
    def setUp(self):
        self.exp = Experiment.objects.create(
            key='hero',
            name='Hero',
            status='running',
            variants=[
                {'name': 'control', 'weight': 50},
                {'name': 'treatment', 'weight': 50},
            ],
            goal='purchase',
        )

    def test_same_visitor_always_same_variant(self):
        r = _request(visitor_cookie='visitor-abc')
        first = variant_for(r, 'hero')
        second = variant_for(r, 'hero')
        third = variant_for(r, 'hero')
        self.assertEqual(first, second)
        self.assertEqual(second, third)

    def test_different_visitors_can_get_different_variants(self):
        seen = set()
        for i in range(40):
            r = _request(visitor_cookie=f'visitor-{i}')
            seen.add(variant_for(r, 'hero'))
        # With 40 visitors and 50/50 weights, P(all same variant) ≈ 2 × 0.5^40.
        self.assertEqual(seen, {'control', 'treatment'})

    def test_unknown_experiment_returns_control(self):
        r = _request(visitor_cookie='visitor-z')
        self.assertEqual(variant_for(r, 'nonexistent_key'), 'control')

    def test_paused_experiment_returns_control(self):
        Experiment.objects.create(
            key='paused',
            name='Paused',
            status='paused',
            variants=[{'name': 'control', 'weight': 1}, {'name': 't', 'weight': 1}],
            goal='purchase',
        )
        r = _request(visitor_cookie='visitor-z')
        self.assertEqual(variant_for(r, 'paused'), 'control')


class WeightDistributionTests(TestCase):
    def test_70_30_distribution_approximate(self):
        Experiment.objects.create(
            key='split7030',
            name='70/30',
            status='running',
            variants=[
                {'name': 'control', 'weight': 70},
                {'name': 'treatment', 'weight': 30},
            ],
            goal='purchase',
        )
        rng = random.Random(0)
        counts = {'control': 0, 'treatment': 0}
        for _ in range(2000):
            visitor = f'visitor-{rng.randrange(0, 10**9)}'
            r = _request(visitor_cookie=visitor)
            counts[variant_for(r, 'split7030')] += 1
        control_share = counts['control'] / 2000
        # Allow ±5% wobble; 70% target.
        self.assertGreater(control_share, 0.65)
        self.assertLess(control_share, 0.75)


class AssignmentPersistenceTests(TestCase):
    def setUp(self):
        self.exp = Experiment.objects.create(
            key='persist',
            name='Persist',
            status='running',
            variants=[
                {'name': 'control', 'weight': 1},
                {'name': 'treatment', 'weight': 1},
            ],
            goal='purchase',
        )

    def test_first_call_writes_assignment_row(self):
        r = _request(visitor_cookie='vp1')
        variant_for(r, 'persist')
        self.assertEqual(
            Assignment.objects.filter(experiment=self.exp, visitor_id='v:vp1').count(),
            1,
        )

    def test_repeat_calls_do_not_duplicate(self):
        r = _request(visitor_cookie='vp2')
        for _ in range(5):
            variant_for(r, 'persist')
        self.assertEqual(
            Assignment.objects.filter(experiment=self.exp, visitor_id='v:vp2').count(),
            1,
        )

    def test_exposure_increments(self):
        r = _request(visitor_cookie='vp3')
        for _ in range(3):
            variant_for(r, 'persist')
        total = sum(e.exposures for e in Exposure.objects.filter(experiment=self.exp))
        self.assertEqual(total, 3)


class ConversionAttributionTests(TestCase):
    def setUp(self):
        self.exp = Experiment.objects.create(
            key='convert',
            name='Convert',
            status='running',
            variants=[
                {'name': 'control', 'weight': 1},
                {'name': 'treatment', 'weight': 1},
            ],
            goal='purchase',
        )

    def test_conversion_attributed_to_assigned_variant(self):
        r = _request(visitor_cookie='vc1')
        assigned = variant_for(r, 'convert')

        record_conversion(
            experiment_key='convert',
            visitor_id='v:vc1',
            revenue=Decimal('50'),
        )

        for_assigned = Exposure.objects.get(experiment=self.exp, variant=assigned)
        self.assertEqual(for_assigned.conversions, 1)
        self.assertEqual(for_assigned.revenue, Decimal('50'))

        for other in Exposure.objects.exclude(variant=assigned):
            self.assertEqual(other.conversions, 0)

    def test_no_assignment_no_conversion(self):
        # Visitor never exposed → record_conversion is a silent no-op.
        record_conversion(
            experiment_key='convert',
            visitor_id='v:never-seen',
        )
        total = sum(e.conversions for e in Exposure.objects.filter(experiment=self.exp))
        self.assertEqual(total, 0)


class ResultsLiftMathTests(TestCase):
    def setUp(self):
        self.exp = Experiment.objects.create(
            key='lift',
            name='Lift',
            status='running',
            variants=[
                {'name': 'control', 'weight': 1},
                {'name': 'treatment', 'weight': 1},
            ],
            goal='purchase',
        )

    def _seed(self, *, variant, exposures, conversions):
        from datetime import date  # noqa: PLC0415

        Exposure.objects.create(
            experiment=self.exp,
            variant=variant,
            day=date(2026, 5, 1),
            exposures=exposures,
            conversions=conversions,
        )

    def test_no_data_does_not_crash(self):
        out = results_for(self.exp)
        self.assertIn('variants', out)
        for v in out['variants']:
            self.assertEqual(v['exposures'], 0)
            self.assertEqual(v['conversions'], 0)
            self.assertIsNone(v['z_score'])

    def test_lift_pct_correct(self):
        self._seed(variant='control', exposures=1000, conversions=50)  # 5%
        self._seed(variant='treatment', exposures=1000, conversions=75)  # 7.5% → +50% lift

        out = results_for(self.exp)
        treatment = next(v for v in out['variants'] if v['variant'] == 'treatment')
        self.assertAlmostEqual(treatment['lift_pct'], 50.0, delta=1.0)
        # Z-score should comfortably cross significance threshold here.
        self.assertGreater(treatment['z_score'], 1.96)
        self.assertTrue(treatment['significant_95'])

    def test_small_sample_no_significance(self):
        self._seed(variant='control', exposures=50, conversions=2)
        self._seed(variant='treatment', exposures=50, conversions=3)
        out = results_for(self.exp)
        treatment = next(v for v in out['variants'] if v['variant'] == 'treatment')
        # Tiny lift on a 50-visitor sample shouldn't trip significance.
        self.assertFalse(treatment['significant_95'])


class VisitorIdResolutionTests(TestCase):
    def test_authenticated_user_uses_user_pk(self):
        from plugins.installed.experiments.services import visitor_id_for  # noqa: PLC0415

        r = _request(user=_AuthUser(pk=42))
        self.assertEqual(visitor_id_for(r), 'u:42')

    def test_anonymous_user_with_cookie(self):
        from plugins.installed.experiments.services import visitor_id_for  # noqa: PLC0415

        r = _request(visitor_cookie='anon-cookie')
        self.assertEqual(visitor_id_for(r), 'v:anon-cookie')

    def test_anonymous_user_no_cookie_mints_one(self):
        from plugins.installed.experiments.services import visitor_id_for  # noqa: PLC0415

        r = _request()
        vid = visitor_id_for(r)
        self.assertTrue(vid.startswith('v:'))
        self.assertTrue(len(vid) > 5)
        # The middleware reads `_set_visitor_cookie` and attaches the cookie.
        self.assertTrue(hasattr(r, '_set_visitor_cookie'))

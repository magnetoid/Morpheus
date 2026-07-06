"""Self-optimizing autopilot bandit (Phase 2).

A per-segment Beta-Bernoulli bandit reranks the propensity grid per visitor and
learns nightly from real product-view engagement (views in converting sessions
score higher). These tests cover the segmentation, the reranker guardrails
(exploration floor, diversity cap, cold-start), the posterior rebuild, and the
`autopilot` strategy end to end.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.analytics.models import AnalyticsEvent, AnalyticsSession
from plugins.installed.catalog.models import Product
from plugins.installed.dynamic_products.models import BanditArm, DynamicBlock, DynamicGridItem
from plugins.installed.dynamic_products.reranker import (
    _cap_by_category,
    _inject_exploration,
    thompson_rerank,
)
from plugins.installed.dynamic_products.segments import segment_of
from plugins.installed.dynamic_products.services import rebuild_bandit_posteriors, recommend

Customer = get_user_model()


def _product(slug):
    return Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal('10.00'), 'USD'),
        status='active',
    )


class SegmentTests(TestCase):
    def test_segment_of_is_deterministic_and_labelled(self):
        self.assertEqual(segment_of('mobile', 20, False), 'mobile:evening:anon')
        self.assertEqual(segment_of('desktop', 8, True), 'desktop:morning:known')
        self.assertEqual(segment_of('weird', 2, False), 'desktop:night:anon')  # unknown → desktop

    def test_segment_for_reads_request(self):
        from plugins.installed.dynamic_products.segments import segment_for

        req = RequestFactory().get('/', HTTP_USER_AGENT='Mozilla/5.0 (iPhone; Mobile)')
        seg = segment_for(req)
        self.assertEqual(seg.split(':')[0], 'mobile')
        self.assertEqual(seg.split(':')[2], 'anon')  # AnonymousUser


class RerankerGuardrailTests(TestCase):
    def test_cap_by_category_limits_head_then_tails_overflow(self):
        # 3 from 'a', 1 from 'b', cap 2 → the 3rd 'a' slides behind 'b'.
        out = _cap_by_category([1, 2, 3, 4], {1: 'a', 2: 'a', 3: 'a', 4: 'b'}, cap=2)
        self.assertEqual(out, [1, 2, 4, 3])

    def test_inject_exploration_is_a_permutation(self):
        out = _inject_exploration([1, 2, 3, 4, 5], 1.0)  # max jitter
        self.assertEqual(sorted(out), [1, 2, 3, 4, 5])

    def test_thompson_rerank_returns_a_permutation_even_cold(self):
        ids = [10, 20, 30]
        out = thompson_rerank(ids, 'mobile:evening:anon', {10: 0.9, 20: 0.1, 30: 0.5})
        self.assertEqual(sorted(out), sorted(ids))

    def test_thompson_rerank_empty_is_safe(self):
        self.assertEqual(thompson_rerank([], 'x', {}), [])


class PosteriorRebuildTests(TestCase):
    def _view(self, session, product):
        return AnalyticsEvent.objects.create(
            name='product.viewed', kind='product_view', product_slug=product.slug, session=session
        )

    def test_converting_sessions_lift_the_arm(self):
        from django.utils import timezone

        hot, cold = _product('hot'), _product('cold')
        # A mobile-anon session that VIEWS hot then converts (purchase).
        s_conv = AnalyticsSession.objects.create(cookie_id='c1', device='mobile')
        self._view(s_conv, hot)
        AnalyticsEvent.objects.create(name='order.placed', kind='purchase', session=s_conv)
        # A mobile-anon session that only VIEWS cold (no conversion).
        s_bounce = AnalyticsSession.objects.create(cookie_id='c2', device='mobile')
        self._view(s_bounce, cold)

        self.assertEqual(rebuild_bandit_posteriors()['updated'], 2)

        seg = segment_of('mobile', timezone.localtime(timezone.now()).hour, False)
        hot_arm = BanditArm.objects.get(product=hot, segment=seg)
        cold_arm = BanditArm.objects.get(product=cold, segment=seg)
        # hot's view converted (reward 1.0) → higher posterior mean than cold (0.1).
        self.assertGreater(hot_arm.reward, cold_arm.reward)
        self.assertGreater(hot_arm.mean, cold_arm.mean)

    def test_rebuild_without_analytics_events_is_safe(self):
        self.assertEqual(rebuild_bandit_posteriors()['updated'], 0)


class AutopilotStrategyTests(TestCase):
    def test_autopilot_returns_products(self):
        a, b = _product('a'), _product('b')
        DynamicGridItem.objects.create(product=a, title='A', purchase_probability=0.8)
        DynamicGridItem.objects.create(product=b, title='B', purchase_probability=0.3)
        block = DynamicBlock.objects.create(
            name='AP', slot='home_below_grid', strategy='autopilot', limit=8
        )
        req = RequestFactory().get('/', HTTP_USER_AGENT='Mozilla/5.0')
        products = recommend(block, request=req)
        self.assertEqual({p.id for p in products}, {a.id, b.id})


class AutomationWiringTests(TestCase):
    def test_bandit_rebuild_task_and_beat_registered(self):
        from django.conf import settings

        from plugins.installed.dynamic_products.tasks import rebuild_bandit_posteriors as task

        self.assertEqual(task.name, 'dynamic_products.rebuild_bandit_posteriors')
        self.assertIn('dynamic_products:rebuild_bandit_posteriors', settings.CELERY_BEAT_SCHEDULE)

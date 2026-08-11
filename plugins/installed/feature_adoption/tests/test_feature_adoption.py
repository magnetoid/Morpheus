"""Tests for feature_adoption: counters/flush, health math, matrix, permissions."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from django.utils import timezone

from plugins.installed.feature_adoption import tracking
from plugins.installed.feature_adoption.models import FeatureUsageDay
from plugins.installed.feature_adoption.tracking import (
    adoption_matrix,
    compute_health,
    install_health,
)
from plugins.installed.feature_adoption.views import adoption_dashboard


class CounterFlushTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_two_hits_flush_to_one_row(self):
        tracking._incr('catalog', 'dashboard')
        tracking._incr('catalog', 'dashboard')
        flushed = tracking.flush_counters()
        self.assertEqual(flushed, 1)
        row = FeatureUsageDay.objects.get(plugin='catalog', surface='dashboard')
        self.assertEqual(row.count, 2)

    def test_flush_is_additive_across_runs(self):
        tracking._incr('orders', 'dashboard')
        tracking.flush_counters()
        tracking._incr('orders', 'dashboard')
        tracking._incr('orders', 'dashboard')
        tracking.flush_counters()
        row = FeatureUsageDay.objects.get(plugin='orders', surface='dashboard')
        self.assertEqual(row.count, 3)

    def test_flush_with_nothing_dirty_is_noop(self):
        self.assertEqual(tracking.flush_counters(), 0)
        self.assertEqual(FeatureUsageDay.objects.count(), 0)

    def test_agent_tool_surface_counts_separately(self):
        tracking._incr('inventory', 'agent_tool')
        tracking.flush_counters()
        row = FeatureUsageDay.objects.get(plugin='inventory', surface='agent_tool')
        self.assertEqual(row.count, 1)


class ResolvePluginTests(TestCase):
    def test_apps_route_resolves_active_plugin(self):
        # 'analytics' is an active plugin in every boot.
        self.assertEqual(tracking.resolve_plugin('/dashboard/apps/analytics/v2/'), 'analytics')

    def test_apps_route_unknown_plugin_is_none(self):
        self.assertIsNone(tracking.resolve_plugin('/dashboard/apps/totally-unknown-xyz/x/'))

    def test_unknown_custom_segment_is_none(self):
        self.assertIsNone(tracking.resolve_plugin('/dashboard/no-such-segment-zzz/'))

    def test_non_dashboard_path_is_none(self):
        self.assertIsNone(tracking.resolve_plugin('/products/foo/'))


class HealthMathTests(TestCase):
    def test_full_score(self):
        h = compute_health(
            plugins_used=10, plugins_enabled=10, agent_calls=100, days_since_dashboard=0
        )
        self.assertEqual(h['score'], 100)
        self.assertEqual(h['components'], {'breadth': 40, 'agent': 30, 'freshness': 30})

    def test_half_breadth_no_agent_no_freshness(self):
        h = compute_health(
            plugins_used=5, plugins_enabled=10, agent_calls=0, days_since_dashboard=None
        )
        self.assertEqual(h['components']['breadth'], 20)
        self.assertEqual(h['components']['agent'], 0)
        self.assertEqual(h['components']['freshness'], 0)
        self.assertEqual(h['score'], 20)

    def test_freshness_linear_decay(self):
        h = compute_health(
            plugins_used=0, plugins_enabled=10, agent_calls=0, days_since_dashboard=7
        )
        self.assertEqual(h['components']['freshness'], 15)  # 30 * (1 - 7/14)

    def test_agent_caps_at_max(self):
        h = compute_health(
            plugins_used=0, plugins_enabled=10, agent_calls=9999, days_since_dashboard=None
        )
        self.assertEqual(h['components']['agent'], 30)

    def test_zero_enabled_does_not_divide_by_zero(self):
        h = compute_health(
            plugins_used=0, plugins_enabled=0, agent_calls=0, days_since_dashboard=None
        )
        self.assertEqual(h['score'], 0)

    def test_install_health_reads_rows(self):
        today = timezone.now().date()
        FeatureUsageDay.objects.create(day=today, plugin='catalog', surface='dashboard', count=5)
        FeatureUsageDay.objects.create(day=today, plugin='orders', surface='agent_tool', count=50)
        h = install_health()
        # dashboard visited today → full freshness.
        self.assertEqual(h['components']['freshness'], 30)
        # 50 agent calls → 30 * 50/100 = 15.
        self.assertEqual(h['components']['agent'], 15)
        self.assertGreater(h['components']['breadth'], 0)


class AdoptionMatrixTests(TestCase):
    def test_window_buckets(self):
        today = timezone.now().date()
        FeatureUsageDay.objects.create(day=today, plugin='catalog', surface='dashboard', count=3)
        FeatureUsageDay.objects.create(
            day=today - timedelta(days=45), plugin='catalog', surface='dashboard', count=7
        )
        data = adoption_matrix()
        row = next(r for r in data['rows'] if r['plugin'] == 'catalog')
        self.assertEqual(row['u7'], 3)
        self.assertEqual(row['u30'], 3)
        self.assertEqual(row['u90'], 10)
        self.assertEqual(len(row['series']), 90)

    def test_never_used_lists_active_unused_plugins(self):
        data = adoption_matrix()
        # Nothing recorded → every active plugin is a deprecation candidate,
        # and 'catalog' (definitely active) is among them.
        self.assertIn('catalog', data['never_used'])


class PermissionTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_dashboard_requires_staff(self):
        req = self.rf.get('/dashboard/apps/feature_adoption/adoption/')
        req.user = AnonymousUser()
        resp = adoption_dashboard(req)
        self.assertIn(resp.status_code, (302, 403))

    def test_dashboard_page_is_contributed_not_hardcoded(self):
        # Disable/delete litmus: the page is registered under this plugin, so
        # the registry drops it on deactivate — it is never hard-coded elsewhere.
        from plugins.registry import app_registry

        pages = [p for p in app_registry.dashboard_pages() if p.plugin == 'feature_adoption']
        self.assertTrue(pages)
        self.assertTrue(all(p.view for p in pages))

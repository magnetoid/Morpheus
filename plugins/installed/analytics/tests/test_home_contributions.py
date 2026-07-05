"""Dashboard-home KPI + activity contributions — hook-bus filters, so a
disabled analytics plugin contributes nothing (disable-safety for free)."""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.hooks import MorpheusEvents, hook_registry
from plugins.installed.analytics.models import AnalyticsEvent, DailyMetric


class HomeKpiTests(TestCase):
    def test_kpis_appended(self):
        yesterday = timezone.now().date() - timedelta(days=1)
        DailyMetric.objects.create(day=yesterday, metric='sessions', value_int=42)
        DailyMetric.objects.create(day=yesterday, metric='conversion_rate', value_int=240)
        kpis = hook_registry.filter(MorpheusEvents.DASHBOARD_KPIS, value=[])
        labels = {k['label'] for k in kpis}
        self.assertIn('Sessions', labels)
        self.assertIn('Conversion rate', labels)
        conv = next(k for k in kpis if k['label'] == 'Conversion rate')
        self.assertEqual(conv['value'], '2.40%')

    def test_activity_feed_surfaces_anomalies(self):
        AnalyticsEvent.objects.create(
            name='analytics.anomaly',
            kind='custom',
            payload={'metric': 'revenue', 'direction': 'down', 'z': 3.4},
        )
        items = hook_registry.filter(MorpheusEvents.ACTIVITY_FEED, value=[], limit=20)
        self.assertTrue(any(i.get('kind') == 'anomaly' for i in items))

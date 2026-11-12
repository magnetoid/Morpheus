"""Dashboard-home KPI + activity contributions — hook-bus filters, so a
disabled analytics plugin contributes nothing (disable-safety for free)."""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.analytics.models import AnalyticsEvent, DailyMetric


class HomeKpiTests(TestCase):
    def test_kpis_appended(self):
        # Today on the store's clock, with no range picked (v0.156.0): visits and
        # the purchases of counted visitors over them.
        from core.utils.site import store_today

        today = store_today()
        DailyMetric.objects.create(day=today, metric='sessions', value_int=50)
        DailyMetric.objects.create(day=today, metric='counted_purchases', value_int=1)
        DailyMetric.objects.create(day=today - timedelta(days=1), metric='sessions', value_int=40)
        kpis = hook_registry.filter(MorpheusEvents.DASHBOARD_KPIS, value=[])
        by_label = {k['label']: k for k in kpis}
        self.assertEqual(by_label['Visits']['value'], '50')
        self.assertEqual(by_label['Visits']['delta'], '+25%')
        self.assertEqual(by_label['Conversion rate']['value'], '2.00%')

    def test_activity_feed_surfaces_anomalies(self):
        AnalyticsEvent.objects.create(
            name='analytics.anomaly',
            kind='custom',
            payload={'metric': 'revenue', 'direction': 'down', 'z': 3.4},
        )
        items = hook_registry.filter(MorpheusEvents.ACTIVITY_FEED, value=[], limit=20)
        self.assertTrue(any(i.get('kind') == 'anomaly' for i in items))

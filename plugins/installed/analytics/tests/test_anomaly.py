"""Anomaly detector v1 — day-of-week robust z-score over DailyMetric.
Must fire on a seeded spike, stay quiet on flat data, and be idempotent."""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from plugins.installed.analytics.models import AnalyticsEvent, DailyMetric
from plugins.installed.analytics.services_anomaly import detect_anomalies


def _seed(metric: str, values: list[int]):
    """values[-1] is 'yesterday'; earlier entries step back one day each."""
    yday = timezone.now().date() - timedelta(days=1)
    for i, v in enumerate(reversed(values)):
        DailyMetric.objects.create(day=yday - timedelta(days=i), metric=metric, value_int=v)


class AnomalyTests(TestCase):
    def test_flat_data_is_quiet(self):
        _seed('orders', [10, 11, 10, 9, 10, 11, 10, 9, 10, 11, 10, 9, 10, 10])
        self.assertEqual(detect_anomalies(), [])

    def test_crash_fires(self):
        _seed('orders', [10, 11, 10, 9, 10, 11, 10, 9, 10, 11, 10, 9, 10, 0])
        findings = detect_anomalies()
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['metric'], 'orders')
        self.assertEqual(findings[0]['direction'], 'down')
        self.assertTrue(AnalyticsEvent.objects.filter(name='analytics.anomaly').exists())

    def test_idempotent_per_metric_day(self):
        _seed('orders', [10, 11, 10, 9, 10, 11, 10, 9, 10, 11, 10, 9, 10, 0])
        detect_anomalies()
        detect_anomalies()
        self.assertEqual(AnalyticsEvent.objects.filter(name='analytics.anomaly').count(), 1)

    def test_too_little_history_is_quiet(self):
        _seed('orders', [10, 0])
        self.assertEqual(detect_anomalies(), [])

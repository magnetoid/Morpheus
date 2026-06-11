"""Rollup correctness tests."""

from __future__ import annotations

from django.test import TestCase

from core.models import OutboxEvent
from plugins.installed.observability.models import MerchantMetric
from plugins.installed.observability.services import rollup, supported_metrics


class RollupTests(TestCase):
    def test_supported_metrics_is_non_empty(self):
        self.assertTrue(supported_metrics())

    def test_rollup_collapses_events_into_buckets(self):
        # Two order.placed events on the same hour should collapse into 1 bucket with value=2.
        OutboxEvent.objects.create(event_type='order.placed', payload={})
        OutboxEvent.objects.create(event_type='order.placed', payload={})
        OutboxEvent.objects.create(event_type='product.viewed', payload={})
        n = rollup(granularity='hour', lookback_hours=1)
        self.assertGreaterEqual(n, 2)
        ordered = MerchantMetric.objects.get(metric='orders_placed', granularity='hour')
        self.assertEqual(ordered.value, 2)
        viewed = MerchantMetric.objects.get(metric='product_views', granularity='hour')
        self.assertEqual(viewed.value, 1)

    def test_rollup_is_idempotent(self):
        OutboxEvent.objects.create(event_type='order.placed', payload={})
        rollup(granularity='hour', lookback_hours=1)
        rollup(granularity='hour', lookback_hours=1)
        self.assertEqual(MerchantMetric.objects.filter(metric='orders_placed').count(), 1)
        self.assertEqual(MerchantMetric.objects.get(metric='orders_placed').value, 1)

"""checkout.started must flow hook → event → rollup, and order.placed must be
the ONLY purchase-kind event (payment.captured double-counted revenue)."""

from __future__ import annotations

from django.test import TestCase
from django.utils import timezone

from core.hooks import MorpheusEvents, hook_registry
from plugins.installed.analytics.models import AnalyticsEvent, DailyMetric
from plugins.installed.analytics.services import roll_daily
from plugins.installed.analytics.tasks import _kind_for


class KindForTests(TestCase):
    def test_checkout_started_maps_to_checkout(self):
        self.assertEqual(_kind_for('checkout.started'), 'checkout')

    def test_only_order_placed_is_purchase(self):
        self.assertEqual(_kind_for('order.placed'), 'purchase')
        self.assertNotEqual(_kind_for('payment.captured'), 'purchase')


class CheckoutHookTests(TestCase):
    def test_begin_checkout_hook_records_event(self):
        hook_registry.fire(MorpheusEvents.BEGIN_CHECKOUT, cart=None, customer=None)
        self.assertTrue(
            AnalyticsEvent.objects.filter(name='checkout.started').exists(),
            'analytics must subscribe to BEGIN_CHECKOUT',
        )


class CheckoutRollupTests(TestCase):
    def test_roll_daily_counts_checkout_started(self):
        AnalyticsEvent.objects.create(name='checkout.started', kind='checkout')
        AnalyticsEvent.objects.filter(name='checkout.started').update(
            created_at=timezone.now() - timezone.timedelta(days=1)
        )
        roll_daily()
        row = DailyMetric.objects.get(metric='checkouts_started', dimension='')
        self.assertEqual(row.value_int, 1)

"""Derived daily KPIs — conversion_rate/aov/cart_abandonment must roll into
DailyMetric so history survives the 90-day raw-event trim."""

from __future__ import annotations

from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.analytics.models import (
    AnalyticsEvent,
    AnalyticsSession,
    DailyMetric,
)
from plugins.installed.analytics.services import roll_daily


class DerivedRollupTests(TestCase):
    def _seed_yesterday(self):
        yesterday = timezone.now() - timezone.timedelta(days=1)
        sessions = [AnalyticsSession.objects.create(cookie_id=f'ck-{i}') for i in range(4)]
        for s in sessions:
            AnalyticsEvent.objects.create(name='pageview', kind='pageview', session=s)
        AnalyticsEvent.objects.create(name='cart.add', kind='cart', session=sessions[0])
        AnalyticsEvent.objects.create(name='cart.add', kind='cart', session=sessions[1])
        AnalyticsEvent.objects.create(name='checkout.started', kind='checkout', session=sessions[0])
        AnalyticsEvent.objects.create(
            name='order.placed',
            kind='purchase',
            session=sessions[0],
            revenue=Money(50, 'USD'),
        )
        AnalyticsEvent.objects.update(created_at=yesterday)

    def test_derived_metrics_written(self):
        self._seed_yesterday()
        roll_daily()
        # 1 purchase / 4 sessions = 25.00% = 2500 bp
        self.assertEqual(DailyMetric.objects.get(metric='conversion_rate').value_int, 2500)
        # revenue 50 / 1 order = 50.00
        self.assertEqual(DailyMetric.objects.get(metric='aov').value_money, Money(50, 'USD'))
        # 1 checkout / 2 cart_adds → abandonment 50.00% = 5000 bp
        self.assertEqual(DailyMetric.objects.get(metric='cart_abandonment').value_int, 5000)

    def test_no_division_by_zero_on_empty_day(self):
        roll_daily()  # nothing seeded — must not raise
        self.assertEqual(DailyMetric.objects.get(metric='conversion_rate').value_int, 0)

"""Multi-touch attribution — exact per-model splits, ROAS, spend collection, page."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.analytics.models import AdSpendSnapshot, DailyMetric
from plugins.installed.analytics.services_attribution import (
    attribute,
    collect_ad_spend,
    roas_by_channel,
)

User = get_user_model()


def _journey():
    now = timezone.now()
    return [
        ('meta', now - timedelta(days=10)),
        ('google', now - timedelta(days=3)),
        ('email', now),
    ]


class AttributeTests(TestCase):
    def test_last_touch(self):
        r = attribute(_journey(), 100, 'last_touch')
        self.assertEqual(r['email'], Decimal('100'))
        self.assertEqual(r['meta'], Decimal('0'))

    def test_first_touch(self):
        r = attribute(_journey(), 100, 'first_touch')
        self.assertEqual(r['meta'], Decimal('100'))
        self.assertEqual(r['email'], Decimal('0'))

    def test_linear(self):
        r = attribute(_journey(), 100, 'linear')
        for ch in ('meta', 'google', 'email'):
            self.assertAlmostEqual(float(r[ch]), 33.333, places=2)
        self.assertAlmostEqual(float(sum(r.values())), 100.0, places=4)

    def test_position_based(self):
        r = attribute(_journey(), 100, 'position_based')
        self.assertEqual(r['meta'], Decimal('40'))
        self.assertEqual(r['email'], Decimal('40'))
        self.assertEqual(r['google'], Decimal('20'))

    def test_time_decay_favors_recency_and_conserves(self):
        r = attribute(_journey(), 100, 'time_decay')
        self.assertGreater(r['email'], r['google'])
        self.assertGreater(r['google'], r['meta'])
        self.assertAlmostEqual(float(sum(r.values())), 100.0, places=4)

    def test_single_touch_gets_everything(self):
        now = timezone.now()
        for model in ('last_touch', 'first_touch', 'linear', 'time_decay', 'position_based'):
            r = attribute([('direct', now)], 100, model)
            self.assertEqual(r['direct'], Decimal('100'), model)


class RoasTests(TestCase):
    def test_roas_from_spend_and_attributed_revenue(self):
        today = timezone.now().date()
        AdSpendSnapshot.objects.create(day=today, channel='meta', spend=Money(Decimal('50'), 'USD'))
        DailyMetric.objects.create(
            day=today,
            metric='attribution',
            dimension='last_touch:meta',
            value_money=Money(Decimal('200'), 'USD'),
        )
        rows = roas_by_channel(model='last_touch')
        meta = next(r for r in rows if r['channel'] == 'meta')
        self.assertEqual(meta['roas'], Decimal('4'))  # 200 / 50

    def test_no_spend_gives_none_roas(self):
        today = timezone.now().date()
        DailyMetric.objects.create(
            day=today,
            metric='attribution',
            dimension='last_touch:organic',
            value_money=Money(Decimal('10'), 'USD'),
        )
        rows = roas_by_channel(model='last_touch')
        organic = next(r for r in rows if r['channel'] == 'organic')
        self.assertIsNone(organic['roas'])


class CollectAdSpendTests(TestCase):
    def test_filter_writes_snapshot(self):
        with patch(
            'core.hooks.hook_registry.filter',
            return_value=[{'channel': 'meta', 'spend': 100, 'days': 30}],
        ):
            written = collect_ad_spend()
        self.assertEqual(written, 1)
        self.assertTrue(AdSpendSnapshot.objects.filter(channel='meta').exists())


class AttributionPageTests(TestCase):
    URL = '/dashboard/analytics/v2/attribution/'

    def test_anon_blocked(self):
        self.assertIn(self.client.get(self.URL).status_code, (301, 302))

    def test_staff_ok(self):
        staff = User.objects.create_user(
            username='bossattr', email='ba@x.io', password='pw', is_staff=True
        )
        self.client.force_login(staff)
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'attribution')

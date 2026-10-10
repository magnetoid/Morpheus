"""Channels overview — filter aggregation + dashboard boundary."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase

User = get_user_model()


class OverviewTests(TestCase):
    def setUp(self):
        cache.delete('channels:overview:v1')
        self.staff = User.objects.create_user(
            username='s', email='s@x.test', password='pw', is_staff=True
        )

    def _staff(self):
        c = Client()
        c.force_login(self.staff)
        return c

    def test_filter_aggregates_every_channel(self):
        from plugins.installed.channels.views import _rows

        rows = _rows(refresh=True)
        names = {r['name'] for r in rows}
        # All nine commerce channels contribute a row.
        self.assertEqual(
            names,
            {
                'google_shopping',
                'meta_commerce',
                'tiktok_commerce',
                'pinterest_commerce',
                'microsoft_commerce',
                'amazon_ads',
                'reddit_ads',
                'snapchat_commerce',
                'openai_shopping',
            },
        )
        # Every row carries the contract keys.
        for r in rows:
            for key in ('label', 'connected', 'has_feed', 'dashboard_url'):
                self.assertIn(key, r)

    def test_boundary_and_render(self):
        self.assertEqual(Client().get('/dashboard/apps/channels/overview/').status_code, 302)
        r = self._staff().get('/dashboard/apps/channels/overview/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Sales Channels')
        self.assertContains(r, 'Snapchat')
        self.assertContains(r, 'Google')

    def test_metrics_merge_and_blended_roas(self):
        from plugins.installed.channels.tasks import METRICS_CACHE_KEY
        from plugins.installed.channels.views import _merge_metrics, _rows

        cache.set(
            METRICS_CACHE_KEY,
            [
                {'name': 'meta_commerce', 'spend': 100.0, 'revenue': 400.0, 'conversions': 10},
                {'name': 'tiktok_commerce', 'spend': 50.0, 'conversions': 3},  # no revenue
            ],
            60,
        )
        rows = _rows(refresh=True)
        self.assertTrue(_merge_metrics(rows))
        by_name = {r['name']: r for r in rows}
        # roas computed from revenue/spend when the channel didn't supply it
        self.assertEqual(by_name['meta_commerce']['metrics']['roas'], 4.0)
        # no revenue → no roas, but spend still present
        self.assertIsNone(by_name['tiktok_commerce']['metrics']['roas'])
        self.assertEqual(by_name['tiktok_commerce']['metrics']['spend'], 50.0)

    def test_refresh_metrics_task_caches_rows(self):
        from plugins.installed.channels.tasks import METRICS_CACHE_KEY, refresh_metrics

        cache.delete(METRICS_CACHE_KEY)
        refresh_metrics()
        # Filter ran; with no channels connected every contributor no-ops to an
        # empty list, which is still a valid cached value (not None).
        self.assertIsNotNone(cache.get(METRICS_CACHE_KEY))


class AttributionTests(TestCase):
    def setUp(self):
        from plugins.installed.channels.tasks import METRICS_CACHE_KEY

        cache.delete(METRICS_CACHE_KEY)

    def _purchase(self, source, amount):
        import uuid
        from decimal import Decimal

        from djmoney.money import Money

        from plugins.installed.analytics.models import AnalyticsEvent, AnalyticsSession

        sess = AnalyticsSession.objects.create(cookie_id=uuid.uuid4().hex, utm_source=source)
        AnalyticsEvent.objects.create(
            name='order.placed',
            kind='purchase',
            session=sess,
            revenue=Money(Decimal(str(amount)), 'USD'),
        )

    def test_revenue_by_source(self):
        from plugins.installed.analytics.services import revenue_by_source

        self._purchase('google', 100)
        self._purchase('tiktok', 40)
        self._purchase('', 60)  # direct / untagged
        rev = revenue_by_source(days=30)
        self.assertEqual(rev['total'], 200.0)
        self.assertEqual(rev['by_source'].get('google'), 100.0)
        self.assertEqual(rev['direct'], 60.0)

    def test_build_attribution_blended_and_lasttouch(self):
        from plugins.installed.channels.attribution import build_attribution
        from plugins.installed.channels.tasks import METRICS_CACHE_KEY

        self._purchase('google', 100)
        self._purchase('', 50)  # direct
        cache.set(
            METRICS_CACHE_KEY,
            [
                {
                    'name': 'google_shopping',
                    'spend': 25.0,
                    'revenue': 80.0,
                    'roas': 3.2,
                    'conversions': 4,
                }
            ],
            60,
        )
        data = build_attribution(days=30)
        self.assertEqual(data['total_revenue'], 150.0)
        self.assertEqual(data['total_spend'], 25.0)
        self.assertEqual(data['blended_roas'], 6.0)  # 150 / 25
        self.assertEqual(data['direct_revenue'], 50.0)
        g = next(r for r in data['rows'] if r['name'] == 'google_shopping')
        self.assertEqual(g['lasttouch_revenue'], 100.0)
        self.assertEqual(g['lasttouch_roas'], 4.0)  # 100 / 25, beats platform-claimed
        self.assertEqual(g['platform_roas'], 3.2)

    def test_view_boundary_and_render(self):
        staff = User.objects.create_user(
            username='attr', email='a@x.test', password='pw', is_staff=True
        )
        self.assertEqual(Client().get('/dashboard/apps/channels/attribution/').status_code, 302)
        c = Client()
        c.force_login(staff)
        r = c.get('/dashboard/apps/channels/attribution/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Blended ROAS')

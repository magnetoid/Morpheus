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
        # All eight commerce channels contribute a row.
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

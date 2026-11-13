"""Channels answers ANALYTICS_AD_SPEND from its daily cache, once per channel."""

from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase

from core.hooks import MorpheusEvents, hook_registry
from plugins.installed.channels.tasks import METRICS_CACHE_KEY
from plugins.registry import app_registry


def _ask():
    return hook_registry.filter(MorpheusEvents.ANALYTICS_AD_SPEND, value=[])


class AdSpendAnswerTests(TestCase):
    def setUp(self):
        self.addCleanup(cache.delete, METRICS_CACHE_KEY)
        cache.set(
            METRICS_CACHE_KEY,
            [
                {
                    'name': 'google_shopping',
                    'spend': 120.0,
                    'revenue': 300.0,
                    'conversions': 4,
                    'clicks': 50,
                    'roas': 2.5,
                },
                {'name': 'tiktok_commerce', 'spend': 0, 'revenue': 0, 'conversions': 0},
            ],
            600,
        )

    def test_one_row_per_channel_with_spend_from_the_cache(self):
        self.assertEqual(
            _ask(),
            [
                {
                    'channel': 'google',
                    'spend': 120.0,
                    'conversions': 4,
                    'platform_revenue': 300.0,
                    'days': 30,
                }
            ],
        )

    def test_no_ad_channel_app_answers_the_hook_itself(self):
        owners = {entry[3] for entry in hook_registry._handlers[MorpheusEvents.ANALYTICS_AD_SPEND]}
        self.assertEqual(owners, {'channels'})

    def test_conversions_are_the_platforms_number_and_absent_stays_none(self):
        cache.set(
            METRICS_CACHE_KEY,
            [
                'junk',
                {'name': 'google_shopping', 'spend': 10.0, 'conversions': 3.5},
                {'name': 'meta_commerce', 'spend': 20.0},
            ],
            600,
        )
        rows = {r['channel']: r for r in _ask()}
        self.assertEqual(rows['google']['conversions'], 3.5)
        self.assertIsNone(rows['meta']['conversions'])
        self.assertIsNone(rows['meta']['platform_revenue'])

    def test_meta_reports_its_purchases_as_conversions(self):
        from unittest.mock import patch

        totals = {'spend': 50.0, 'clicks': 9, 'purchases': 2.5, 'value': 80.0, 'roas': 1.6}
        with patch(
            'plugins.installed.meta_commerce.services.ads_api.campaign_report',
            return_value={'ok': True, 'totals': totals},
        ):
            rows = hook_registry.filter(MorpheusEvents.CHANNELS_METRICS, value=[])
        meta = next(r for r in rows if r['name'] == 'meta_commerce')
        self.assertEqual(meta['conversions'], 2.5)

    def test_empty_cache_answers_nothing(self):
        cache.delete(METRICS_CACHE_KEY)
        self.assertEqual(_ask(), [])

    def test_channels_off_answers_nothing(self):
        app_registry.deactivate('channels')
        self.addCleanup(app_registry.activate, 'channels')
        self.assertEqual(_ask(), [])

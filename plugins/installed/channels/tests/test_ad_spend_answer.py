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

    def test_google_and_meta_add_no_row_of_their_own(self):
        cache.set(
            METRICS_CACHE_KEY,
            [
                {'name': 'google_shopping', 'spend': 10.0},
                {'name': 'meta_commerce', 'spend': 20.0},
            ],
            600,
        )
        rows = _ask()
        self.assertEqual(sorted(r['channel'] for r in rows), ['google', 'meta'])
        self.assertEqual(len(rows), 2)
        # A value the platform did not report stays absent, never 0.
        self.assertIsNone(rows[0]['conversions'])
        self.assertIsNone(rows[0]['platform_revenue'])

    def test_empty_cache_answers_nothing(self):
        cache.delete(METRICS_CACHE_KEY)
        self.assertEqual(_ask(), [])

    def test_channels_off_answers_nothing(self):
        app_registry.deactivate('channels')
        self.addCleanup(app_registry.activate, 'channels')
        self.assertEqual(_ask(), [])

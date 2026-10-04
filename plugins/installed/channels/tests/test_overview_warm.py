"""The channels overview never computes feed coverage on a request.

Each channel's ``coverage_report()`` walks every active product with several
queries per product (8,257 queries and 6.5 s for 861 products on one store), and
the overview asked six channels in a row: 49 s for one page. The reports are
cached for an hour and ``channels.refresh_overview`` recomputes them every half
hour, so the page reads a snapshot.
"""

from __future__ import annotations

import importlib

from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

CHANNELS = (
    'google_shopping',
    'meta_commerce',
    'tiktok_commerce',
    'pinterest_commerce',
    'microsoft_commerce',
    'snapchat_commerce',
)


class CoverageCacheTests(TestCase):
    def test_a_repeat_coverage_report_runs_no_queries(self):
        for channel in CHANNELS:
            with self.subTest(channel=channel):
                mod = importlib.import_module(f'plugins.installed.{channel}.services.coverage')
                cache.clear()
                with CaptureQueriesContext(connection) as first:
                    report = mod.coverage_report()
                self.assertGreater(len(first.captured_queries), 0)
                with self.assertNumQueries(0):
                    again = mod.coverage_report()
                self.assertEqual(again, report)


class RefreshOverviewTests(TestCase):
    def test_the_task_fills_the_overview_cache(self):
        from plugins.installed.channels.tasks import refresh_overview

        cache.delete('channels:overview:v1')
        refresh_overview()
        rows = cache.get('channels:overview:v1')
        self.assertIsInstance(rows, list)
        self.assertGreaterEqual(len(rows), 1)

    def test_the_task_is_scheduled_under_its_registered_name(self):
        from morph.celery import app

        entry = app.conf.beat_schedule.get('channels:refresh_overview')
        self.assertIsNotNone(entry)
        self.assertEqual(entry['task'], 'channels.refresh_overview')
        self.assertLessEqual(entry['schedule'], 60 * 30)

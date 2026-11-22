"""A theme setting can be saved, and every worker sees it within 10 seconds.

Until v0.185.0 nothing could save a theme setting except a database write, and
each process read a theme's settings once and kept them until it restarted: a
save made in one web worker never reached the others or the Celery worker.
"""

from __future__ import annotations

import time
from unittest.mock import patch

from django.test import TestCase

from themes.base import MorpheusTheme
from themes.models import ThemeConfig
from themes.registry import theme_registry


class ThemeConfigSaveTests(TestCase):
    def setUp(self):
        self.theme = theme_registry.active
        self.addCleanup(self.theme.invalidate_config_cache)
        self.theme.invalidate_config_cache()

    def test_set_config_stores_the_value_and_this_process_reads_it_at_once(self):
        self.theme.get_config()  # warm the cache, as a page render would
        self.theme.set_config('tagline', 'A new line')

        self.assertEqual(self.theme.get_config_value('tagline'), 'A new line')
        row = ThemeConfig.objects.get(theme_name=self.theme.name)
        self.assertEqual(row.config['tagline'], 'A new line')

    def test_the_first_save_creates_the_row_without_activating_the_theme(self):
        # A theme switched on by MORPHEUS_ACTIVE_THEME has no row yet.
        self.assertFalse(ThemeConfig.objects.filter(theme_name=self.theme.name).exists())
        active_before = theme_registry.active.name

        self.theme.set_config('tagline', 'A new line')

        row = ThemeConfig.objects.get(theme_name=self.theme.name)
        self.assertIs(row.is_active, False)
        self.assertEqual(theme_registry.active.name, active_before)

    def test_another_worker_sees_a_save_within_ten_seconds(self):
        other = type(self.theme)()  # the same theme, loaded by another process
        self.addCleanup(other.invalidate_config_cache)
        start = time.monotonic()
        with patch('themes.base.time.monotonic', return_value=start):
            other.get_config()
            self.theme.set_config('tagline', 'Fresh')
        with patch('themes.base.time.monotonic', return_value=start + 9.0):
            self.assertNotEqual(other.get_config_value('tagline'), 'Fresh')
        with patch('themes.base.time.monotonic', return_value=start + 10.0):
            self.assertEqual(other.get_config_value('tagline'), 'Fresh')

    def test_themes_re_read_their_settings_every_ten_seconds(self):
        self.assertEqual(MorpheusTheme.config_fresh_s, 10.0)

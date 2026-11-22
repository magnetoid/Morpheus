"""Dawnchild's Christmas look (v0.186.0).

Three theme settings decide it: `christmas_look` (off, dates or on) and the two
days, written DD-MM, between which `dates` shows it every year on the store's
clock. The rule lives in `themes/library/dawnchild/christmas.py`; the theme's
`christmas_on()` reads it for the templates.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase, TestCase

from plugins import config_schema
from themes.library.dawnchild.christmas import is_on, parse_day
from themes.registry import theme_registry

DATES = {'christmas_look': 'dates'}


class ChristmasDayRuleTests(SimpleTestCase):
    def test_the_default_is_off(self):
        self.assertIs(is_on({}, date(2026, 12, 25)), False)

    def test_on_shows_it_any_day(self):
        self.assertIs(is_on({'christmas_look': 'on'}, date(2026, 7, 1)), True)

    def test_dates_use_the_default_range_across_new_year(self):
        for day, expected in (
            (date(2026, 11, 30), False),
            (date(2026, 12, 1), True),
            (date(2026, 12, 31), True),
            (date(2027, 1, 1), True),
            (date(2027, 1, 6), True),
            (date(2027, 1, 7), False),
        ):
            with self.subTest(day=day):
                self.assertIs(is_on(DATES, day), expected)

    def test_dates_inside_one_year(self):
        config = {**DATES, 'christmas_from': '10-12', 'christmas_until': '24-12'}
        for day, expected in (
            (date(2026, 12, 9), False),
            (date(2026, 12, 10), True),
            (date(2026, 12, 24), True),
            (date(2026, 12, 25), False),
        ):
            with self.subTest(day=day):
                self.assertIs(is_on(config, day), expected)

    def test_a_date_that_is_not_a_day_falls_back_to_its_default(self):
        for bad in ('31-02', '1 Dec', '', '00-12', '12-13'):
            with self.subTest(bad=bad):
                config = {**DATES, 'christmas_from': bad}
                self.assertIs(is_on(config, date(2026, 12, 1)), True)
                self.assertIs(is_on(config, date(2026, 11, 30)), False)
        self.assertEqual(parse_day('29-02'), (2, 29))
        self.assertEqual(parse_day('01-12'), (12, 1))
        self.assertIsNone(parse_day('31-02'))

    def test_an_unknown_mode_is_off(self):
        self.assertIs(is_on({'christmas_look': 'yes'}, date(2026, 12, 25)), False)

    def test_the_schema_declares_the_three_settings(self):
        props = theme_registry.get('dawnchild').get_config_schema()['properties']
        self.assertEqual(props['christmas_look']['enum'], ['off', 'dates', 'on'])
        self.assertEqual(props['christmas_look']['default'], 'off')
        self.assertEqual(props['christmas_from']['default'], '01-12')
        self.assertEqual(props['christmas_until']['default'], '06-01')
        for key, example in (('christmas_from', '01-12'), ('christmas_until', '06-01')):
            self.assertEqual(props[key]['pattern'], r'\d{2}-\d{2}')
            self.assertEqual(props[key]['examples'], [example])

    def test_linda_cannot_store_a_date_not_written_dd_mm(self):
        prop = theme_registry.get('dawnchild').get_config_schema()['properties']['christmas_from']
        with self.assertRaises(config_schema.SettingError) as ctx:
            config_schema.clean('christmas_from', prop, '1 Dec')
        self.assertIn('01-12', str(ctx.exception))
        self.assertEqual(config_schema.clean('christmas_from', prop, '24-12'), '24-12')


class ChristmasStoreClockTests(TestCase):
    def test_the_store_clock_decides_the_day(self):
        theme = theme_registry.get('dawnchild')
        theme.invalidate_config_cache()
        self.addCleanup(theme.invalidate_config_cache)
        theme.set_config('christmas_look', 'dates')
        late = datetime(2026, 11, 30, 23, 30, tzinfo=UTC)
        with (
            patch('core.utils.site.store_timezone', return_value=ZoneInfo('Europe/Belgrade')),
            patch('django.utils.timezone.now', return_value=late),
        ):
            self.assertIs(theme.christmas_on(), True)

"""Automations take a five-field cron schedule, read on the store's clock.

The plan (W3, docs/plans/morpheus-improvement-plan-2026-10.md) asked for cron
syntax on Automations: "every weekday at nine" or "the 1st and 15th" could not
be said with an interval or one time a day. croniter is not a dependency, so
agent_core parses the five fields itself (agent_core/cron.py).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from plugins.installed.agent_core import cron

BELGRADE = ZoneInfo('Europe/Belgrade')


def _at(*parts):
    return datetime(*parts, tzinfo=BELGRADE)


class CronNextRunTests(SimpleTestCase):
    def _next(self, expr, after):
        return cron.parse(expr).next_after(after)

    def test_weekday_mornings_skip_the_weekend(self):
        # Saturday 2026-10-10, 10:00 → Monday 09:00.
        self.assertEqual(self._next('0 9 * * 1-5', _at(2026, 10, 10, 10, 0)), _at(2026, 10, 12, 9))

    def test_the_next_run_is_strictly_after_the_moment(self):
        self.assertEqual(self._next('0 9 * * *', _at(2026, 10, 12, 9, 0)), _at(2026, 10, 13, 9))

    def test_steps_ranges_and_lists(self):
        self.assertEqual(
            self._next('*/15 * * * *', _at(2026, 10, 12, 10, 7)), _at(2026, 10, 12, 10, 15)
        )
        self.assertEqual(
            self._next('0 8-18/5 * * *', _at(2026, 10, 12, 8, 30)), _at(2026, 10, 12, 13)
        )
        self.assertEqual(
            self._next('30 8 1,15 * *', _at(2026, 10, 2, 0, 0)), _at(2026, 10, 15, 8, 30)
        )

    def test_month_and_day_names(self):
        # Sunday noon in January or July: from 2026-10-12 the first is 2027-01-03.
        self.assertEqual(
            self._next('0 12 * jan,jul sun', _at(2026, 10, 12, 0, 0)), _at(2027, 1, 3, 12)
        )

    def test_seven_is_sunday_too(self):
        self.assertEqual(self._next('0 6 * * 7', _at(2026, 10, 12, 0, 0)), _at(2026, 10, 18, 6))

    def test_both_day_fields_set_means_either_one(self):
        # As in cron itself: the 13th OR a Friday. Monday 12 → Tuesday 13.
        self.assertEqual(self._next('0 0 13 * 5', _at(2026, 10, 12, 1, 0)), _at(2026, 10, 13))
        # ...and after the 13th, the Friday comes first.
        self.assertEqual(self._next('0 0 13 * 5', _at(2026, 10, 13, 1, 0)), _at(2026, 10, 16))


class CronParseErrorTests(SimpleTestCase):
    def _error(self, expr) -> str:
        with self.assertRaises(ValueError) as caught:
            cron.parse(expr)
        return str(caught.exception)

    def test_five_fields_are_required(self):
        self.assertIn('five fields', self._error('0 9 * *'))
        self.assertIn('five fields', self._error(''))

    def test_out_of_range_values_name_their_field(self):
        self.assertIn('minute', self._error('60 * * * *'))
        self.assertIn('hour', self._error('0 24 * * *'))
        self.assertIn('month', self._error('0 0 1 13 *'))

    def test_bad_steps_ranges_and_words(self):
        self.assertIn('step', self._error('*/0 * * * *'))
        self.assertIn('minute', self._error('5-1 * * * *'))
        self.assertIn('"every"', self._error('every * * * *'))

    def test_a_schedule_that_never_fires_is_refused(self):
        self.assertIn('never', self._error('0 0 31 2 *'))


class LindaMinimumTests(SimpleTestCase):
    def test_a_linda_cron_may_not_fire_more_often_than_every_fifteen_minutes(self):
        self.assertIn('15 minutes', cron.schedule_error('*/5 * * * *', engine='linda'))
        self.assertIn('15 minutes', cron.schedule_error('0,10 9 * * *', engine='linda'))
        self.assertEqual(cron.schedule_error('*/15 * * * *', engine='linda'), '')
        self.assertEqual(cron.schedule_error('0 9 * * 1-5', engine='linda'), '')

    def test_a_worker_cron_keeps_its_minute(self):
        self.assertEqual(cron.schedule_error('* * * * *', engine='worker'), '')

    def test_a_bad_expression_is_reported_not_raised(self):
        self.assertIn('five fields', cron.schedule_error('0 9 *', engine='linda'))


class CronSchedulingTests(TestCase):
    def test_schedule_next_follows_the_cron_on_the_store_clock(self):
        from plugins.installed.agent_core.models import BackgroundAgent
        from plugins.installed.agent_core.scheduler import schedule_next

        job = BackgroundAgent.objects.create(
            name='Weekday report', prompt='Report.', engine='linda', cron='0 9 * * 1-5'
        )
        now = _at(2026, 10, 10, 10, 0)  # a Saturday
        with (
            mock.patch(
                'plugins.installed.agent_core.scheduler._store_timezone', return_value=BELGRADE
            ),
            mock.patch('django.utils.timezone.now', return_value=now),
        ):
            schedule_next(job)
        job.refresh_from_db()
        self.assertEqual(job.next_run_at, _at(2026, 10, 12, 9))

    def test_the_first_run_of_a_cron_automation_waits_for_its_slot(self):
        from plugins.installed.agent_core.models import BackgroundAgent
        from plugins.installed.agent_core.scheduler import first_run_at

        job = BackgroundAgent(name='x', prompt='x', engine='linda', cron='0 9 * * *')
        self.assertGreater(first_run_at(job), timezone.now())
        self.assertLessEqual(first_run_at(job) - timezone.now(), timedelta(days=1))
        # An interval automation runs on the next tick, as it always has.
        job = BackgroundAgent(name='x', prompt='x', engine='linda', interval_seconds=3600)
        self.assertLessEqual(first_run_at(job), timezone.now())

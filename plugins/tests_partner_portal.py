"""The partner-portal helpers: comparisons that never divide by zero, chart
geometry that never reaches CSS as a localised number, and a period that only
takes the values the page offers."""

from __future__ import annotations

from decimal import Decimal

from django.test import RequestFactory, SimpleTestCase, override_settings
from django.utils import translation

from plugins import partner_portal as pp


class ChangeTests(SimpleTestCase):
    def test_nothing_to_compare(self):
        self.assertIsNone(pp.change(0, 0))
        self.assertIsNone(pp.change_points(Decimal('0'), Decimal('0')))

    def test_from_nothing_is_new_not_infinite(self):
        self.assertEqual(pp.change(5, 0)['dir'], 'up')
        self.assertNotIn('%', pp.change(5, 0)['text'])

    def test_percent_and_points(self):
        self.assertEqual(pp.change(150, 100), {'dir': 'up', 'text': '50%'})
        self.assertEqual(pp.change(Decimal('75'), Decimal('100')), {'dir': 'down', 'text': '25%'})
        self.assertEqual(pp.change(100, 100)['dir'], 'flat')
        self.assertEqual(pp.change_points(Decimal('3.2'), Decimal('4.0'))['dir'], 'down')


class GeometryTests(SimpleTestCase):
    @override_settings(USE_THOUSAND_SEPARATOR=True)
    def test_bar_heights_are_plain_strings_in_any_language(self):
        period = pp.period_from(RequestFactory().get('/?days=7'))
        with translation.override('sr'):
            chart = pp.bar_chart([1, 2, 3, 0, 0, 0, 4], period, fmt=str)
        heights = [bar['h'] for bar in chart['bars']]
        self.assertEqual(heights[:3], ['25.0', '50.0', '75.0'])
        self.assertTrue(chart['bars'][3]['zero'])
        self.assertFalse(any(',' in h for h in heights))

    def test_a_flat_series_has_no_sparkline(self):
        self.assertEqual(pp.sparkline([0, 0, 0]), {})
        line = pp.sparkline([1, 3, 2])
        self.assertEqual(len(line['points'].split()), 3)
        self.assertNotIn(',,', line['points'])


class PeriodTests(SimpleTestCase):
    def test_only_the_offered_periods(self):
        factory = RequestFactory()
        self.assertEqual(pp.period_from(factory.get('/?days=90')).days, 90)
        self.assertEqual(pp.period_from(factory.get('/?days=5')).days, pp.DEFAULT_PERIOD)
        self.assertEqual(pp.period_from(factory.get('/?days=x')).days, pp.DEFAULT_PERIOD)
        period = pp.period_from(factory.get('/?days=7'))
        self.assertEqual(len(period.dates), 7)
        self.assertEqual((period.start - period.prev_start).days, 7)

    def test_initials(self):
        self.assertEqual(pp.initials('Hill Apothecary'), 'HA')
        self.assertEqual(pp.initials('@jane-wellness'), 'JW')
        self.assertEqual(pp.initials(''), '·')

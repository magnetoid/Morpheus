"""`|business_days` prints a delivery range in business days (F5).

The checkout's shipping choices, the order pages and the placed email read the
same filter, so a range reads the same everywhere and no app imports another
for the wording.
"""

from __future__ import annotations

from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils import translation


def render(value) -> str:
    return Template('{% load morph %}{{ v|business_days }}').render(Context({'v': value}))


class BusinessDaysTests(SimpleTestCase):
    def test_a_range(self):
        self.assertEqual(render({'min': 3, 'max': 7}), '3–7 business days')

    def test_equal_ends(self):
        self.assertEqual(render({'min': 3, 'max': 3}), '3 business days')

    def test_one_day(self):
        self.assertEqual(render({'min': 1, 'max': 1}), '1 business day')

    def test_a_range_ending_in_one_is_plural(self):
        self.assertEqual(render({'min': 0, 'max': 1}), '0–1 business days')

    def test_unusable_values_print_nothing(self):
        for value in (
            None,
            {},
            {'min': 'x', 'max': 2},
            {'min': -1, 'max': 2},
            {'min': 5, 'max': 2},
            {'min': True, 'max': 2},
            'abc',
        ):
            self.assertEqual(render(value), '', value)

    def test_serbian_and_croatian(self):
        for lang in ('sr', 'hr'):
            with translation.override(lang):
                out = render({'min': 3, 'max': 7})
            self.assertIn('3–7', out, lang)
            self.assertNotIn('business', out, lang)

"""List fields, dates and paths in a language (v0.191.0).

An experience's highlights, itinerary and guest questions are JSON lists. A
translator edits them as text (one line per item; a blank line between pairs) and
the page shows them as the lists they are, so the template keeps its loops.
"""

from __future__ import annotations

import datetime

from django.test import SimpleTestCase, override_settings

from core.i18n.dates import babel_locale, format_day
from core.i18n.services import clean_value, from_text, is_list_kind, pair_keys, to_text
from core.utils.i18n import path_in_language


class ListKindTests(SimpleTestCase):
    def test_kinds(self):
        self.assertEqual(pair_keys('pairs:q,a'), ('q', 'a'))
        self.assertIsNone(pair_keys('pairs:q'))
        self.assertIsNone(pair_keys('text'))
        self.assertTrue(is_list_kind('lines'))
        self.assertTrue(is_list_kind('pairs:title,detail'))
        self.assertFalse(is_list_kind('html'))

    def test_lines_round_trip(self):
        text = to_text('lines', ['Guide', '  Snacks  and water ', ''])
        self.assertEqual(text, 'Guide\nSnacks and water')
        self.assertEqual(
            from_text('lines', 'Vodič\r\n\r\nUžina i voda\n'), ['Vodič', 'Užina i voda']
        )

    def test_pairs_round_trip_keeps_the_other_keys(self):
        original = [
            {'time': '09:00', 'title': 'Meet', 'detail': 'At the pier.'},
            {'time': '10:00', 'title': 'Paddle', 'detail': 'Across the bay.\nTo the cave.'},
        ]
        text = to_text('pairs:title,detail', original)
        self.assertEqual(text, 'Meet\nAt the pier.\n\nPaddle\nAcross the bay.\nTo the cave.')
        shown = from_text(
            'pairs:title,detail', 'Sastanak\nNa molu.\n\nVeslanje\nPreko zaliva.', original
        )
        self.assertEqual(
            shown,
            [
                {'time': '09:00', 'title': 'Sastanak', 'detail': 'Na molu.'},
                {'time': '10:00', 'title': 'Veslanje', 'detail': 'Preko zaliva.'},
            ],
        )

    def test_a_question_without_an_answer(self):
        self.assertEqual(from_text('pairs:q,a', 'Pitanje?'), [{'q': 'Pitanje?', 'a': ''}])

    def test_not_a_list_reads_as_nothing(self):
        self.assertEqual(to_text('lines', 'not a list'), '')
        self.assertEqual(to_text('pairs:q,a', [1, 'x']), '')

    def test_clean_value_keeps_the_shape_and_drops_markup(self):
        cleaned = clean_value(
            None, 'faqs', 'pairs:q,a', '<b>Pitanje?</b>\r\nOdgovor.\r\n\r\n\r\nDrugo?\nDa.'
        )
        self.assertEqual(cleaned, 'Pitanje?\nOdgovor.\n\nDrugo?\nDa.')


class DateTests(SimpleTestCase):
    def test_serbian_is_latin(self):
        self.assertEqual(babel_locale('sr'), 'sr_Latn')
        day = datetime.date(2026, 11, 8)
        self.assertIn('novembar', format_day(day, language='sr'))
        self.assertIn('November', format_day(day, language='en'))
        self.assertEqual(format_day(None), '')

    def test_an_unknown_code_reads_as_english(self):
        self.assertEqual(babel_locale('xx_nonsense'), 'en')


@override_settings(LANGUAGE_CODE='en', LANGUAGES=[('en', 'English'), ('sr', 'Srpski')])
class PathInLanguageTests(SimpleTestCase):
    def test_paths(self):
        self.assertEqual(path_in_language('/journal/x/', 'sr'), '/sr/journal/x/')
        self.assertEqual(path_in_language('/journal/x/', 'en'), '/journal/x/')
        self.assertEqual(path_in_language('/journal/x/', ''), '/journal/x/')
        self.assertEqual(path_in_language('/journal/x/', 'de'), '/journal/x/')
        self.assertEqual(path_in_language('/sr/journal/x/', 'sr'), '/sr/journal/x/')
        self.assertEqual(path_in_language('https://x.test/a/', 'sr'), 'https://x.test/a/')

"""Anti-template gate for experience copy — titles varied, descriptions deep."""

import re

from django.test import SimpleTestCase

from plugins.installed.booking_marketplace.management.commands._experiences_data import (
    LEGACY_COPY,
    NEW_EXPERIENCES,
)


def _all_titles():
    return [e['name'] for e in NEW_EXPERIENCES] + [c['name'] for c in LEGACY_COPY.values()]


class TitleQualityTests(SimpleTestCase):
    def test_titles_unique(self):
        titles = _all_titles()
        self.assertEqual(len(titles), len(set(titles)))

    def test_title_lengths(self):
        for t in _all_titles():
            self.assertTrue(20 <= len(t) <= 70, f'bad length: {t!r} ({len(t)})')

    def test_formula_caps(self):
        titles = _all_titles()
        self.assertLessEqual(sum(1 for t in titles if '—' in t), 10, 'too many em-dash titles')
        self.assertLessEqual(
            sum(1 for t in titles if re.search(r'from [A-ZŽĐŠĆČ]\w+$', t)),
            5,
            'too many "from X" titles',
        )
        self.assertLessEqual(
            sum(1 for t in titles if re.search(r'\b(tour|trip|experience)\b', t, re.I)),
            20,
            'too many tour/trip/experience titles',
        )

    def test_legacy_copy_covers_all_20(self):
        self.assertEqual(len(LEGACY_COPY), 20)
        for slug, c in LEGACY_COPY.items():
            self.assertEqual(set(c) - {'name'}, {'short_description', 'description'}, slug)


class DescriptionQualityTests(SimpleTestCase):
    def test_two_paragraphs_450_to_700_chars(self):
        entries = [(e['slug'], e['description']) for e in NEW_EXPERIENCES]
        entries += [(s, c['description']) for s, c in LEGACY_COPY.items()]
        for slug, d in entries:
            self.assertIn('\n\n', d, f'{slug}: single paragraph')
            self.assertTrue(450 <= len(d) <= 700, f'{slug}: {len(d)} chars')

    def test_short_description_not_title_parrot(self):
        for e in NEW_EXPERIENCES:
            self.assertNotEqual(
                e['short_description'].strip().lower(), e['name'].strip().lower(), e['slug']
            )

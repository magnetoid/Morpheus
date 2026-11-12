"""`Content-Language` names the page's language, and Serbian dates are Latin (v0.160.0).

The header was set from the market or `LANGUAGE_CODE` before Django's own
LocaleMiddleware could name the active language, so every /sr/ page said `en`.
Django's `sr` catalog is Cyrillic, so `|date` printed "суб." and "Окт." on the
Latin /sr/ pages; the store's catalog carries the Latin names (from Django's
sr_Latn) and outranks it.
"""

from __future__ import annotations

import datetime
import re

from django.template import Context, Template
from django.test import TestCase, override_settings
from django.utils import translation

BILINGUAL = {'LANGUAGES': [('en', 'English'), ('sr', 'Srpski')], 'LANGUAGE_CODE': 'en'}
_CYRILLIC = re.compile('[Ѐ-ӿ]')


@override_settings(**BILINGUAL)
class ContentLanguageTests(TestCase):
    def test_a_serbian_page_says_sr(self):
        self.assertEqual(self.client.get('/sr/')['Content-Language'], 'sr')

    def test_an_english_page_says_en(self):
        self.assertEqual(self.client.get('/')['Content-Language'], 'en')


class LatinDateTests(TestCase):
    def test_a_serbian_date_is_latin(self):
        with translation.override('sr'):
            text = Template('{{ d|date:"D j M Y" }} {{ d|date:"l, F" }} {{ d|date:"N" }}').render(
                Context({'d': datetime.date(2026, 10, 10)})
            )
        self.assertIsNone(_CYRILLIC.search(text), text)
        self.assertIn('sub', text.lower())
        self.assertIn('okt', text.lower())
        self.assertIn('subota', text)
        self.assertIn('oktobar', text)

    @override_settings(**BILINGUAL)
    def test_a_journal_date_follows_the_page_language(self):
        from plugins.installed.cms.models import Page
        from plugins.installed.cms.services import journal_dict

        page = Page.objects.create(
            slug='spring-notes',
            title='Spring notes',
            state='published',
            body='<p>Words.</p>',
            metadata={'category': 'journal'},
            publish_at=datetime.datetime(2026, 10, 10, 12, tzinfo=datetime.UTC),
        )
        self.assertTrue(journal_dict(page)['date_label'].startswith('October 10, 2026'))
        with translation.override('sr'):
            label = journal_dict(page)['date_label']
        self.assertIn('oktobar', label)
        self.assertIsNone(_CYRILLIC.search(label), label)

"""A page written in a store language is not offered for translation into it (v0.191.0)."""

from __future__ import annotations

from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from plugins.installed.cms.models import Page
from plugins.installed.localization.tests.test_translations_page import BILINGUAL, INDEX, _user


@override_settings(**BILINGUAL)
class SourceLanguageEditorTests(TestCase):
    def setUp(self):
        cache.clear()
        self.page = Page.objects.create(
            slug='vodic', title='Vodič', state='published', body='<p>Tekst.</p>', language='sr'
        )
        self.client = Client()
        self.client.force_login(_user('owner', staff=True))

    def test_a_serbian_page_has_nothing_to_translate_into(self):
        for language in ('sr', 'en'):
            url = f'{INDEX}cms.page/{self.page.pk}/{language}/'
            self.assertEqual(self.client.get(url).status_code, 404, language)

    def test_the_serbian_list_leaves_out_pages_written_in_serbian(self):
        Page.objects.create(slug='guide', title='Guide', state='published', body='<p>Text.</p>')
        body = self.client.get(f'{INDEX}?kind=cms.page&language=sr').content.decode()
        self.assertIn('Guide', body)
        self.assertNotIn('Vodič', body)

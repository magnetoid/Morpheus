"""A page says which language it is written in, and the journal lists it there (v0.191.0).

Montenegro's journal holds about forty articles written in Serbian. Until v0.191.0
every page was assumed to be English: the Serbian articles sat in the English
journal under an English canonical, and /sr/journal/ listed every English article.
A page now carries `language` (blank = the store's default); a journal shows the
posts written in the page's language or translated into it.
"""

from __future__ import annotations

import datetime

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone, translation

from core.i18n.services import content_languages, set_translation
from plugins.installed.cms.models import Page
from plugins.installed.cms.services import journal_dict, journal_pages

BILINGUAL = {'LANGUAGES': [('en', 'English'), ('sr', 'Srpski')], 'LANGUAGE_CODE': 'en'}


def _post(slug, title, *, language=''):
    return Page.objects.create(
        slug=slug,
        title=title,
        state='published',
        body=f'<p>{title} body.</p>',
        language=language,
        publish_at=timezone.now() - datetime.timedelta(days=1),
        metadata={'category': 'journal'},
    )


@override_settings(**BILINGUAL)
class JournalLanguageTests(TestCase):
    def setUp(self):
        cache.clear()
        self.english = _post('kotor-guide', 'Kotor guide')
        self.serbian = _post('vodic-za-kotor', 'Vodič za Kotor', language='sr')

    def _slugs(self, language):
        return {p.slug for p in journal_pages(language)}

    def test_each_journal_lists_its_own_language(self):
        self.assertEqual(self._slugs('en'), {'kotor-guide'})
        self.assertEqual(self._slugs('sr'), {'vodic-za-kotor'})

    def test_a_translated_post_joins_the_other_journal(self):
        for field, text in (('title', 'Kotor vodič'), ('body', '<p>Tekst.</p>')):
            set_translation(self.english, field, 'sr', text)
        self.assertEqual(self._slugs('sr'), {'kotor-guide', 'vodic-za-kotor'})

    def test_a_one_language_store_lists_everything(self):
        with self.settings(LANGUAGES=[('en', 'English')]):
            self.assertEqual(self._slugs('en'), {'kotor-guide', 'vodic-za-kotor'})

    def test_a_serbian_post_exists_in_serbian_only(self):
        self.assertEqual(content_languages(self.serbian), {'sr'})
        self.assertEqual(content_languages(self.english), {'en'})

    def test_the_serbian_post_names_its_serbian_address(self):
        cache.clear()
        head = Client().get('/journal/vodic-za-kotor/').content.decode().split('</head>', 1)[0]
        self.assertIn('rel="canonical" href="http://testserver/sr/journal/vodic-za-kotor/"', head)
        cache.clear()
        head = Client().get('/sr/journal/vodic-za-kotor/').content.decode().split('</head>', 1)[0]
        self.assertIn('rel="canonical" href="http://testserver/sr/journal/vodic-za-kotor/"', head)

    def test_the_index_pages(self):
        cache.clear()
        english = Client().get('/journal/').content.decode()
        self.assertIn('/journal/kotor-guide/', english)
        self.assertNotIn('vodic-za-kotor', english)
        cache.clear()
        serbian = Client().get('/sr/journal/').content.decode()
        self.assertIn('vodic-za-kotor', serbian)
        self.assertNotIn('/journal/kotor-guide/', serbian)

    def test_sitemaps_name_the_serbian_address_and_language(self):
        from plugins.installed.seo.services.sitemaps import (
            render_news_sitemap_xml,
            render_sitemap_xml,
        )

        sitemap = render_sitemap_xml()
        self.assertIn('/sr/journal/vodic-za-kotor/</loc>', sitemap)
        self.assertIn('/journal/kotor-guide/</loc>', sitemap)
        news = render_news_sitemap_xml()
        serbian = news.split('/sr/journal/vodic-za-kotor/', 1)[1].split('</url>', 1)[0]
        self.assertIn('<news:language>sr</news:language>', serbian)
        english = news.split('/journal/kotor-guide/', 1)[1].split('</url>', 1)[0]
        self.assertIn('<news:language>en</news:language>', english)


class DateLabelTests(TestCase):
    def test_reading_time_and_date_in_the_page_language(self):
        page = _post('dated', 'Dated')
        page.publish_at = datetime.datetime(2026, 7, 3, 9, 0, tzinfo=datetime.UTC)
        page.body = '<p>' + ('word ' * 1000) + '</p>'
        page.save()
        with translation.override('sr'):
            label = journal_dict(page)['date_label']
        self.assertIn('jul', label)
        self.assertIn('minuta čitanja', label)
        with translation.override('en'):
            self.assertIn('July 3, 2026 · ', journal_dict(page)['date_label'])


@override_settings(**BILINGUAL)
class PageFormLanguageTests(TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_superuser('ed', 'ed@example.com', 'pw')
        self.client = Client()
        self.client.force_login(staff)
        self.page = _post('about-kotor', 'About Kotor')

    def _post_form(self, **extra):
        return self.client.post(
            f'/dashboard/cms/pages/{self.page.id}/edit/',
            {
                'title': 'About Kotor',
                'slug': 'about-kotor',
                'excerpt': '',
                'body': '<p>Tekst</p>',
                'state': 'published',
                'layout': 'default',
                'publish_at': '',
                **extra,
            },
        )

    def test_the_editor_asks_and_saves_the_language(self):
        form = self.client.get(f'/dashboard/cms/pages/{self.page.id}/edit/').content.decode()
        self.assertIn('name="language"', form)
        self.assertEqual(self._post_form(language='sr').status_code, 302)
        self.page.refresh_from_db()
        self.assertEqual(self.page.language, 'sr')
        # A form that does not send it keeps what the page says.
        self._post_form()
        self.page.refresh_from_db()
        self.assertEqual(self.page.language, 'sr')

    def test_a_one_language_store_does_not_ask(self):
        with self.settings(LANGUAGES=[('en', 'English')]):
            form = self.client.get(f'/dashboard/cms/pages/{self.page.id}/edit/').content.decode()
        self.assertNotIn('name="language"', form)

    def test_the_agent_tools_read_and_write_the_language(self):
        from plugins.installed.cms.agent_tools import get_page_tool, update_page_tool

        update_page_tool.invoke({'slug': 'about-kotor', 'language': 'sr', 'confirmed': True})
        self.page.refresh_from_db()
        self.assertEqual(self.page.language, 'sr')
        self.assertEqual(get_page_tool.invoke({'slug': 'about-kotor'}).output['language'], 'sr')

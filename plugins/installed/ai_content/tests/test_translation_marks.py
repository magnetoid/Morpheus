"""A translation an AI drafted is marked where it is shown, and only then (v0.177.0).

EU AI Act Art. 50: a page that shows an object in a reviewed translation that
began as an AI draft carries the same mark as AI-written product text: the
``data-ai-generated`` attribute and a CreativeWork with ``digitalSourceType`` in
its structured data. A person's translation, the default-language page and an
untranslated object carry none.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase, override_settings
from djmoney.money import Money

from core.agents.provenance import mark_ai_written
from core.i18n.services import set_translation
from plugins.installed.ai_content.seo_graph import GENERATED
from plugins.installed.catalog.models import Product
from plugins.registry import app_registry

BILINGUAL = {'LANGUAGES': [('en', 'English'), ('sr', 'Srpski')], 'LANGUAGE_CODE': 'en'}
TRANSLATED_LABEL = "This product's text was translated with the help of AI."
_LD = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)


def _graph_nodes(body: str) -> list[dict]:
    nodes = []
    for raw in _LD.findall(body):
        data = json.loads(raw)
        nodes += data.get('@graph', [data]) if isinstance(data, dict) else []
    return nodes


def _works(body: str) -> list[dict]:
    return [n for n in _graph_nodes(body) if n.get('@type') == 'CreativeWork']


@override_settings(**BILINGUAL)
class ProductPageTests(TestCase):
    def setUp(self):
        cache.clear()
        self.product = Product.objects.create(
            name='Night Sky Atlas',
            slug='night-sky-atlas',
            sku='NSA-1',
            price=Money(Decimal('12.00'), 'USD'),
            product_type='simple',
            status='active',
            short_description='<p>Every constellation, mapped.</p>',
            description='<p>A field guide to the stars.</p>',
        )

    def _body(self, path: str) -> str:
        cache.clear()
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def _translate(self, *, machine: bool):
        for field, text in (
            ('name', 'Atlas noćnog neba'),
            ('short_description', '<p>Sva sazvežđa.</p>'),
            ('description', '<p>Vodič kroz zvezde.</p>'),
        ):
            set_translation(self.product, field, 'sr', text, machine_translated=machine)

    def test_an_ai_translation_is_marked_on_the_serbian_page(self):
        self._translate(machine=True)
        body = self._body('/sr/products/night-sky-atlas/')
        self.assertIn('Vodič kroz zvezde.', body)
        self.assertIn('data-ai-generated="name short_description description"', body)
        works = _works(body)
        self.assertEqual(
            {w['text'] for w in works}, {'Atlas noćnog neba', 'Sva sazvežđa.', 'Vodič kroz zvezde.'}
        )
        self.assertTrue(all(w['digitalSourceType'] == GENERATED for w in works))
        product = next(n for n in _graph_nodes(body) if 'Product' in str(n.get('@type')))
        self.assertNotIn('digitalSourceType', product)
        self.assertEqual(len(product['subjectOf']), 3)

    def test_the_english_page_is_not_marked(self):
        self._translate(machine=True)
        body = self._body('/products/night-sky-atlas/')
        self.assertNotIn('data-ai-generated', body)
        self.assertNotIn(GENERATED, body)

    def test_a_persons_translation_is_not_marked(self):
        self._translate(machine=False)
        body = self._body('/sr/products/night-sky-atlas/')
        self.assertIn('Vodič kroz zvezde.', body)
        self.assertNotIn('data-ai-generated', body)
        self.assertNotIn(GENERATED, body)

    def test_a_persons_translation_of_ai_text_is_the_persons(self):
        mark_ai_written(self.product, ['description', 'short_description'], 'linda')
        self._translate(machine=False)
        body = self._body('/sr/products/night-sky-atlas/')
        self.assertIn('Vodič kroz zvezde.', body)
        self.assertNotIn('data-ai-generated', body)
        self.assertNotIn(GENERATED, body)
        # The English page still shows the AI's own text, so it keeps the mark.
        body = self._body('/products/night-sky-atlas/')
        self.assertIn('data-ai-generated="description short_description"', body)

    def test_a_partial_translation_is_not_shown_and_not_marked(self):
        set_translation(self.product, 'name', 'sr', 'Atlas noćnog neba', machine_translated=True)
        body = self._body('/sr/products/night-sky-atlas/')
        self.assertNotIn('data-ai-generated', body)
        self.assertNotIn(GENERATED, body)

    def test_the_merchant_can_say_it_in_words(self):
        self._translate(machine=True)
        plugin = app_registry.get('ai_content')
        plugin.set_config('label_ai_text', True)
        self.addCleanup(plugin.set_config, 'label_ai_text', False)
        body = self._body('/sr/products/night-sky-atlas/')
        # Serbian page: the sentence in Serbian.
        self.assertIn('Tekst ovog proizvoda preveden je uz pomoć vještačke inteligencije.', body)
        self.assertNotIn(TRANSLATED_LABEL, body)

    def test_a_person_rewriting_the_text_clears_the_mark(self):
        self._translate(machine=True)
        set_translation(self.product, 'description', 'sr', '<p>Moj vodič.</p>')
        body = self._body('/sr/products/night-sky-atlas/')
        self.assertIn('data-ai-generated="name short_description"', body)
        self.assertNotIn('Moj vodič.', {w['text'] for w in _works(body)})


@override_settings(**BILINGUAL)
class ContentPageTests(TestCase):
    """A CMS page: no description block, so the mark is at the end of the body."""

    def setUp(self):
        cache.clear()
        from plugins.installed.cms.models import Page

        self.page = Page.objects.create(
            title='Our Story',
            slug='our-story',
            excerpt='How the shop began.',
            body='<p>It began with one shelf.</p>',
            state='published',
        )

    def _body(self, path: str) -> str:
        cache.clear()
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def _translate(self, *, machine: bool):
        for field, text in (
            ('title', 'Naša priča'),
            ('excerpt', 'Kako je radnja počela.'),
            ('body', '<p>Počelo je jednom policom.</p>'),
        ):
            set_translation(self.page, field, 'sr', text, machine_translated=machine)

    def test_an_ai_translation_is_marked_on_the_serbian_page(self):
        self._translate(machine=True)
        body = self._body('/sr/p/our-story/')
        self.assertIn('Počelo je jednom policom.', body)
        self.assertIn('data-ai-generated="title excerpt body"', body)
        works = _works(body)
        self.assertIn('Počelo je jednom policom.', {w['text'] for w in works})
        self.assertTrue(all(w['digitalSourceType'] == GENERATED for w in works))
        ids = {n.get('@id') for n in _graph_nodes(body)}
        self.assertTrue(all(w['about']['@id'] in ids for w in works))

    def test_a_persons_translation_and_the_english_page_are_not_marked(self):
        self._translate(machine=False)
        for path in ('/sr/p/our-story/', '/p/our-story/'):
            body = self._body(path)
            self.assertNotIn('data-ai-generated', body, path)
            self.assertNotIn(GENERATED, body, path)


@override_settings(**BILINGUAL)
class MarkTranslationsSettingTests(TestCase):
    """The merchant may stop marking AI-drafted translations (v0.193.0).

    The EU's guidelines on Article 50 (C/2026/6005) count translation as standard
    editing, so the mark is the store's choice. Off, the page keeps the marks of an
    object's own AI-written text and drops only those a translation brought.
    """

    def setUp(self):
        from plugins.testing import set_app_settings

        cache.clear()
        set_app_settings(self, 'ai_content', mark_ai_translations=False)
        self.product = Product.objects.create(
            name='Night Sky Atlas',
            slug='night-sky-atlas',
            sku='NSA-1',
            price=Money(Decimal('12.00'), 'USD'),
            product_type='simple',
            status='active',
            short_description='<p>Every constellation, mapped.</p>',
            description='<p>A field guide to the stars.</p>',
        )

    def _body(self, path: str) -> str:
        cache.clear()
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_an_ai_translation_is_not_marked(self):
        for field, text in (
            ('name', 'Atlas noćnog neba'),
            ('short_description', '<p>Sva sazvežđa.</p>'),
            ('description', '<p>Vodič kroz zvezde.</p>'),
        ):
            set_translation(self.product, field, 'sr', text, machine_translated=True)
        body = self._body('/sr/products/night-sky-atlas/')
        self.assertIn('Vodič kroz zvezde.', body)
        self.assertNotIn('data-ai-generated', body)
        self.assertNotIn(GENERATED, body)

    def test_a_content_page_translation_is_not_marked(self):
        from plugins.installed.cms.models import Page

        page = Page.objects.create(
            title='Our Story', slug='our-story', body='<p>One shelf.</p>', state='published'
        )
        set_translation(page, 'title', 'sr', 'Naša priča', machine_translated=True)
        set_translation(page, 'body', 'sr', '<p>Jedna polica.</p>', machine_translated=True)
        body = self._body('/sr/p/our-story/')
        self.assertIn('Jedna polica.', body)
        self.assertNotIn('data-ai-generated', body)
        self.assertNotIn(GENERATED, body)

    def test_the_products_own_ai_text_is_still_marked(self):
        mark_ai_written(self.product, ['description'], 'linda')
        body = self._body('/products/night-sky-atlas/')
        self.assertIn('data-ai-generated="description"', body)
        self.assertIn(GENERATED, body)


class MarkTranslationsEveryWorkerTests(TestCase):
    """A switch saved in another worker reaches this one once the window passes."""

    def setUp(self):
        from plugins.models import PluginConfig

        self.plugin = app_registry.get('ai_content')
        self.plugin.invalidate_config_cache()
        self.addCleanup(self.plugin.invalidate_config_cache)
        self.row, _ = PluginConfig.objects.get_or_create(plugin_name='ai_content')

    def _saved_in_another_worker(self, value: bool):
        from plugins.models import PluginConfig

        # A queryset update: the row changes and this process's cache does not.
        config = {**(self.row.config or {}), 'mark_ai_translations': value}
        PluginConfig.objects.filter(pk=self.row.pk).update(config=config)

    def test_the_switch_reaches_this_worker(self):
        from unittest import mock

        from plugins.installed.ai_content.marks import ai_translated_fields

        with mock.patch('core.i18n.services.ai_translated', return_value=['title']):
            self._saved_in_another_worker(True)
            self.assertEqual(ai_translated_fields(object()), ['title'])
            self._saved_in_another_worker(False)
            self.assertEqual(ai_translated_fields(object()), ['title'])
            self.plugin._config_read_at -= self.plugin.config_fresh_s
            self.assertEqual(ai_translated_fields(object()), [])

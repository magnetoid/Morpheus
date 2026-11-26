"""An outside translator works through MCP: list, read, write (v0.192.0).

The owner translates the stores with ChatGPT over MCP. The generic tools had no
way to read the text to translate, named an object by a content type while the
status tool named it by kind, wrote one field per approved call, and stored a
field or language no page would ever show (a typo, or English on a page written
in Serbian) without a word.
"""

from __future__ import annotations

import json
import uuid

from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from core.agents import ToolError
from core.i18n.agent_tools import (
    set_translation_tool,
    set_translations_tool,
    source_text_tool,
    translation_status_tool,
)
from plugins.installed.cms.models import Page

BILINGUAL = {'LANGUAGES': [('en', 'English'), ('sr', 'Srpski')], 'LANGUAGE_CODE': 'en'}
TOKEN = 'mph_translator-tools-test-token-0123456789abcdef'


def _page(**extra):
    return Page.objects.create(
        slug=extra.pop('slug', 'kotor-guide'),
        title=extra.pop('title', 'Kotor guide'),
        state='published',
        body='<p>The <b>old town</b>.</p>',
        **extra,
    )


@override_settings(**BILINGUAL)
class TranslatorToolTests(TestCase):
    def setUp(self):
        self.page = _page()

    def test_status_names_each_object_the_way_the_other_tools_take_it(self):
        out = translation_status_tool.handler(kind='cms.page', language_code='sr').output
        row = next(o for o in out['objects'] if o['id'] == str(self.page.pk))
        self.assertEqual(row['kind'], 'cms.page')
        self.assertEqual(row['content_type'], 'cms.page')
        self.assertEqual(row['url'], '/p/kotor-guide/')
        self.assertEqual(row['name'], 'Kotor guide')

    def test_source_text_then_set_translations(self):
        src = source_text_tool.handler(
            content_type='cms.page', object_id=str(self.page.pk), language_code='sr'
        ).output
        self.assertEqual(set(src['fields']), {'title', 'body'})
        self.assertEqual(src['fields']['body']['format'], 'html')
        self.page.refresh_from_db()
        self.assertEqual(src['fields']['body']['source'], self.page.body)
        self.assertFalse(src['shown_in_language'])
        self.assertEqual(sorted(src['missing']), ['body', 'title'])

        out = set_translations_tool.handler(
            content_type='cms.page',
            object_id=str(self.page.pk),
            language_code='sr',
            values={'title': 'Vodič za Kotor'},
        ).output
        self.assertEqual(out['missing'], ['body'])
        self.assertFalse(out['shown_in_language'])
        out = set_translations_tool.handler(
            content_type='cms.page',
            object_id=str(self.page.pk),
            language_code='sr',
            values={'body': '<p>Stari <b>grad</b>.</p>'},
        ).output
        self.assertEqual(out['missing'], [])
        self.assertTrue(out['shown_in_language'])
        again = source_text_tool.handler(
            content_type='cms.page', object_id=str(self.page.pk), language_code='sr'
        ).output
        self.assertEqual(again['fields']['title']['translation'], 'Vodič za Kotor')
        self.assertTrue(again['fields']['title']['published'])

    def test_a_field_no_page_shows_is_refused(self):
        with self.assertRaisesMessage(ToolError, 'not translatable here'):
            set_translations_tool.handler(
                content_type='cms.page',
                object_id=str(self.page.pk),
                language_code='sr',
                values={'tittle': 'Vodič'},
            )
        with self.assertRaisesMessage(ToolError, 'not translatable here'):
            set_translation_tool.handler(
                content_type='cms.page',
                object_id=str(self.page.pk),
                field='slug',
                language_code='sr',
                value='vodic',
            )

    def test_a_page_is_not_translated_into_its_own_language_or_the_default(self):
        serbian = _page(slug='vodic', title='Vodič', language='sr')
        for language in ('sr', 'en'):
            with self.assertRaisesMessage(ToolError, 'written in sr'):
                source_text_tool.handler(
                    content_type='cms.page', object_id=str(serbian.pk), language_code=language
                )
            with self.assertRaisesMessage(ToolError, 'written in sr'):
                set_translations_tool.handler(
                    content_type='cms.page',
                    object_id=str(serbian.pk),
                    language_code=language,
                    values={'title': 'Guide'},
                )

    def test_an_empty_text_removes_a_translation(self):
        target = {'content_type': 'cms.page', 'object_id': str(self.page.pk), 'language_code': 'sr'}
        set_translations_tool.handler(**target, values={'title': 'Vodič'})
        out = set_translations_tool.handler(**target, values={'title': ''}).output
        self.assertIn('title', out['missing'])


@override_settings(**BILINGUAL)
class TranslatorOverMcpTests(TestCase):
    """The path ChatGPT takes: a token with the translation scopes, on /mcp/admin/v1/."""

    def setUp(self):
        from plugins.models import PluginConfig

        cache.clear()
        PluginConfig.objects.update_or_create(
            plugin_name='agent_mcp',
            defaults={
                'config': {
                    'public_keys': [
                        {
                            'id': str(uuid.uuid4()),
                            'label': 'translator',
                            'token': TOKEN,
                            'mcp_scopes': ['i18n.read', 'i18n.write'],
                            'approved_tools': ['i18n.set_translations'],
                        }
                    ]
                }
            },
        )
        self.page = _page()

    def _rpc(self, method, params=None):
        body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}})
        return (
            Client()
            .post(
                '/mcp/admin/v1/',
                data=body,
                content_type='application/json',
                HTTP_AUTHORIZATION=f'Bearer {TOKEN}',
            )
            .json()
        )

    def _call(self, name, arguments):
        result = self._rpc('tools/call', {'name': name, 'arguments': arguments})['result']
        self.assertFalse(result.get('isError'), result)
        return result

    def test_the_token_lists_reads_and_writes(self):
        listed = {t['name'] for t in self._rpc('tools/list')['result']['tools']}
        for name in ('i18n.translation_status', 'i18n.source_text', 'i18n.set_translations'):
            self.assertIn(name, listed)
        target = {'content_type': 'cms.page', 'object_id': str(self.page.pk), 'language_code': 'sr'}
        self._call('i18n.source_text', target)
        self._call(
            'i18n.set_translations',
            {**target, 'values': {'title': 'Vodič za Kotor', 'body': '<p>Stari grad.</p>'}},
        )
        from core.i18n.services import content_languages

        self.assertEqual(content_languages(self.page), {'en', 'sr'})

    def test_the_token_page_offers_the_writes_for_approval(self):
        from plugins.installed.agent_mcp.dashboard import _approval_tool_names

        names = _approval_tool_names()
        self.assertIn('i18n.set_translations', names)
        self.assertIn('i18n.set_translation', names)

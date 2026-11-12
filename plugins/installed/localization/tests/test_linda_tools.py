"""Linda's translation tools: status, AI drafts and approval (Janus rule, v0.160.0)."""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from djmoney.money import Money

from core.agents import ToolError
from core.agents.llm import LLMResponse, MockLLMProvider
from core.agents.registry import agent_registry
from core.i18n.models import Translation
from core.i18n.services import content_languages, set_translation

BILINGUAL = {'LANGUAGES': [('en', 'English'), ('sr', 'Srpski')], 'LANGUAGE_CODE': 'en'}


def _product():
    from plugins.installed.catalog.models import Product

    return Product.objects.create(
        name='Harbour Map',
        slug='harbour-map',
        sku='HM-1',
        price=Money(Decimal('9.00'), 'EUR'),
        status='active',
        description='<p>Every quay, drawn.</p>',
    )


@override_settings(**BILINGUAL)
class ToolTests(TestCase):
    def setUp(self):
        cache.clear()
        self.product = _product()

    def _tool(self, name):
        tool = agent_registry.get_tool(name)
        self.assertIsNotNone(tool, name)
        return tool

    def test_the_tools_and_their_gates(self):
        status = self._tool('i18n.translation_status')
        self.assertEqual(status.scopes, ['i18n.read'])
        self.assertFalse(status.requires_approval)
        for name in ('i18n.draft_translations', 'i18n.approve_translation'):
            tool = self._tool(name)
            self.assertEqual(tool.scopes, ['i18n.write'], name)
            self.assertTrue(tool.requires_approval, name)

    def test_status_counts_and_lists_the_missing(self):
        result = self._tool('i18n.translation_status').handler(kind='catalog.product')
        row = next(r for r in result.output['summary'] if r['key'] == 'catalog.product')
        self.assertEqual((row['total'], row['missing'], row['translated']), (1, 1, 0))
        self.assertEqual(result.output['objects'][0]['id'], str(self.product.pk))

    def test_draft_then_approve_publishes(self):
        provider = MockLLMProvider(
            [LLMResponse(text=json.dumps({'name': 'Mapa', 'description': '<p>Gat.</p>'}))]
        )
        with patch('core.agents.llm.get_llm_provider', return_value=provider):
            result = self._tool('i18n.draft_translations').handler(
                kind='catalog.product', language_code='sr'
            )
        self.assertEqual(result.output['queued'], 1)
        self.assertEqual(content_languages(self.product), {'en'})
        approved = self._tool('i18n.approve_translation').handler(
            kind='catalog.product', object_id=str(self.product.pk), language_code='sr'
        )
        self.assertEqual(approved.output['approved'], 2)
        self.assertEqual(content_languages(self.product), {'en', 'sr'})
        self.assertTrue(all(r.is_machine_translated for r in Translation.objects.all()))

    def test_a_language_the_store_lacks_is_refused(self):
        with self.assertRaises(ToolError):
            self._tool('i18n.draft_translations').handler(
                kind='catalog.product', language_code='de'
            )

    def test_set_translation_is_reviewed(self):
        set_translation(self.product, 'name', 'sr', 'Mapa')
        self.assertTrue(Translation.objects.get().reviewed)

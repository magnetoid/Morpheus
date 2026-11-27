"""catalog.fill_missing_content never saves an outage or setup message as copy,
and marks the copy it does write as written with AI (EU AI Act Art. 50)."""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from djmoney.money import Money

from core.agents.llm import (
    DEGRADED_SENTINEL_CIRCUIT,
    LLMProvider,
    LLMResponse,
    _make_unconfigured_mock,
)
from morpheus.core import ToolError, agent_registry
from plugins.installed.agent_core.tools import content
from plugins.installed.catalog.models import Product


class _Replies(LLMProvider):
    name = 'replies'
    model = 'gpt-4o'

    def __init__(self, *texts):
        self.texts = list(texts)

    def respond(self, **_kw):
        return LLMResponse(text=self.texts.pop(0), model='gpt-4o')


class FillMissingContentOutageTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Outage', slug='outage-tool', sku='OT', price=Money(1, 'USD')
        )

    def _fill(self, provider, context=None):
        with patch.object(content, 'get_llm_provider', return_value=provider):
            return agent_registry.get_tool('catalog.fill_missing_content').invoke(
                {'slug': 'outage-tool'}, agent=None, context=context or {}
            )

    def _assert_empty(self):
        self.product.refresh_from_db()
        self.assertEqual(self.product.short_description, '')
        self.assertEqual(self.product.description, '')

    def test_an_outage_saves_nothing_and_says_so(self):
        outage = f'{DEGRADED_SENTINEL_CIRCUIT} — circuit open. retry in 30s]'
        with self.assertRaises(ToolError):
            self._fill(_Replies(outage, outage))
        self._assert_empty()

    def test_no_ai_provider_saves_nothing_and_says_so(self):
        with self.assertRaises(ToolError):
            self._fill(_make_unconfigured_mock('No AI provider selected. Open Settings.'))
        self._assert_empty()

    def test_written_copy_is_marked_as_written_with_ai(self):
        with patch('core.agents.provenance.mark_ai_written') as mark:
            out = self._fill(
                _Replies('A short line.', 'A longer description.'), context={'source': 'linda'}
            ).output
        self.assertEqual(out['products'][0]['updated'], ['short_description', 'description'])
        self.product.refresh_from_db()
        mark.assert_called_once_with(self.product, ['short_description', 'description'], 'linda')

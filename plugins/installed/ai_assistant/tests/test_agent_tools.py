"""ai_assistant contributes flag-gated agent tools.

`catalog.semantic_search` appears in Linda's catalogue only when the
`enable_semantic_search` flag is on, and is callable (falls back to keyword
search when no embeddings exist).
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.ai_assistant.plugin import AIAssistantPlugin


class _FakeLLM:
    model = 'fake'

    def __init__(self, raw='{"labels": ["Fiction"]}'):
        self._raw = raw

    def complete(self, prompt, system='', **kw):
        return self._raw

    def embed(self, text):
        return []


class SemanticSearchToolGatingTests(TestCase):
    def setUp(self):
        self.plugin = AIAssistantPlugin()

    def _tool_names(self):
        return {t.name for t in self.plugin.contribute_agent_tools()}

    def test_tool_absent_when_flag_off(self):
        self.plugin.set_config('enable_semantic_search', False)
        self.assertNotIn('catalog.semantic_search', self._tool_names())

    def test_tool_present_when_flag_on(self):
        self.plugin.set_config('enable_semantic_search', True)
        tools = {t.name: t for t in self.plugin.contribute_agent_tools()}
        self.assertIn('catalog.semantic_search', tools)
        self.assertEqual(tools['catalog.semantic_search'].scopes, ['catalog.read'])

    def test_tool_is_callable(self):
        self.plugin.set_config('enable_semantic_search', True)
        tool = next(
            t for t in self.plugin.contribute_agent_tools() if t.name == 'catalog.semantic_search'
        )
        result = tool.invoke({'query': 'a cosy book for winter evenings', 'limit': 5})
        # Empty catalog → keyword fallback → no products, but a well-formed result.
        self.assertIn('products', result.output)
        self.assertFalse(result.output['used_embedding'])
        self.assertIsInstance(result.output['products'], list)


class ZeroShotToolGatingTests(TestCase):
    def setUp(self):
        self.plugin = AIAssistantPlugin()

    def _tool_names(self):
        return {t.name for t in self.plugin.contribute_agent_tools()}

    def test_tool_absent_when_flag_off(self):
        self.plugin.set_config('enable_zero_shot_catalog', False)
        self.assertNotIn('catalog.classify_product', self._tool_names())

    def test_tool_present_when_flag_on(self):
        self.plugin.set_config('enable_zero_shot_catalog', True)
        tools = {t.name: t for t in self.plugin.contribute_agent_tools()}
        self.assertIn('catalog.classify_product', tools)
        self.assertEqual(tools['catalog.classify_product'].scopes, ['catalog.read'])

    def test_tool_classifies_product_against_categories(self):
        from plugins.installed.catalog.models import Category, Product

        Category.objects.create(name='Fiction', slug='fiction')
        Category.objects.create(name='Science', slug='science')
        Product.objects.create(
            name='Dune',
            slug='dune',
            sku='DUNE1',
            price=Money(Decimal('9.00'), 'USD'),
            product_type='simple',
            status='active',
        )
        self.plugin.set_config('enable_zero_shot_catalog', True)
        tool = next(
            t for t in self.plugin.contribute_agent_tools() if t.name == 'catalog.classify_product'
        )
        with patch(
            'plugins.installed.ai_assistant.services.llm.get_llm',
            return_value=_FakeLLM('{"labels": ["Fiction", "Nonexistent"]}'),
        ):
            result = tool.invoke({'slug': 'dune'})
        # Only candidate labels survive — the hallucinated "Nonexistent" is dropped.
        self.assertEqual(result.output['labels'], ['Fiction'])
        self.assertEqual(result.output['name'], 'Dune')

    def test_tool_unknown_slug_is_clean_error(self):
        self.plugin.set_config('enable_zero_shot_catalog', True)
        tool = next(
            t for t in self.plugin.contribute_agent_tools() if t.name == 'catalog.classify_product'
        )
        result = tool.invoke({'slug': 'does-not-exist'})
        self.assertEqual(result.output['labels'], [])
        self.assertIn('no product', result.output['error'])


class AutonomyGateTests(TestCase):
    """ai_assistant answers the scheduler's AUTONOMY_ENABLED filter from the
    enable_autonomous_operator flag (OR-preserving so it never vetoes another
    enabler)."""

    def setUp(self):
        self.plugin = AIAssistantPlugin()

    def test_gate_off_by_default(self):
        self.plugin.set_config('enable_autonomous_operator', False)
        self.assertFalse(self.plugin._autonomy_gate(False))

    def test_gate_on_when_flag_set(self):
        self.plugin.set_config('enable_autonomous_operator', True)
        self.assertTrue(self.plugin._autonomy_gate(False))

    def test_gate_preserves_upstream_true(self):
        self.plugin.set_config('enable_autonomous_operator', False)
        self.assertTrue(self.plugin._autonomy_gate(True))


class ZeroShotServiceTests(TestCase):
    def test_empty_inputs_short_circuit_without_calling_llm(self):
        from plugins.installed.ai_assistant.services import zero_shot

        called = {'n': 0}

        def _boom():
            called['n'] += 1
            raise AssertionError('LLM must not be called for empty inputs')

        with patch('plugins.installed.ai_assistant.services.llm.get_llm', _boom):
            self.assertEqual(zero_shot.classify('', ['A'])['labels'], [])
            self.assertEqual(zero_shot.classify('text', [])['labels'], [])
        self.assertEqual(called['n'], 0)

    def test_labels_deduped_and_capped(self):
        from plugins.installed.ai_assistant.services import zero_shot

        with patch(
            'plugins.installed.ai_assistant.services.llm.get_llm',
            return_value=_FakeLLM('{"labels": ["Fiction", "fiction", "Drama", "Poetry"]}'),
        ):
            res = zero_shot.classify('a play', ['Fiction', 'Drama', 'Poetry'], max_labels=2)
        # Case-insensitive dedup of Fiction/fiction, then capped at max_labels=2.
        self.assertEqual(res['labels'], ['Fiction', 'Drama'])

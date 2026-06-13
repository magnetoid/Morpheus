"""ai_assistant contributes flag-gated agent tools.

`catalog.semantic_search` appears in Linda's catalogue only when the
`enable_semantic_search` flag is on, and is callable (falls back to keyword
search when no embeddings exist).
"""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.ai_assistant.plugin import AIAssistantPlugin


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

"""LLM provider layer (`core/agents/llm.py`).

Covers tool-schema rendering, the MockLLMProvider scripting contract, the
silent malformed-tool-arg JSON fallback (locked here so Phase 4 can decide to
surface it), and graceful resolution of an unknown provider.
"""

from __future__ import annotations

from types import SimpleNamespace

from django.test import SimpleTestCase

from core.agents.llm import (
    LLMMessage,
    LLMResponse,
    MockLLMProvider,
    OpenAIProvider,
    get_llm_provider,
)
from core.agents.tools import Tool


class ToolSchemaTests(SimpleTestCase):
    def setUp(self):
        self.tool = Tool(
            name='catalog.find',
            description='Find products',
            handler=lambda **kw: None,
            schema={'type': 'object', 'properties': {'q': {'type': 'string'}}},
        )

    def test_openai_schema(self):
        # Schemas carry the provider-safe api_name — OpenAI/Anthropic both
        # reject dots in tool names (pattern ^[a-zA-Z0-9_-]+$).
        s = self.tool.to_openai_schema()
        self.assertEqual(s['type'], 'function')
        self.assertEqual(s['function']['name'], 'catalog__find')
        self.assertIn('q', s['function']['parameters']['properties'])

    def test_anthropic_schema(self):
        s = self.tool.to_anthropic_schema()
        self.assertEqual(s['name'], 'catalog__find')
        self.assertIn('q', s['input_schema']['properties'])

    def test_api_name_matches_provider_pattern_for_all_registered_tools(self):
        # Every tool the platform actually registers must serialize to a name
        # Anthropic/OpenAI accept — this is what turned into the prod
        # "[All AI providers degraded … String should match pattern]" failure.
        import re

        pattern = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')  # 64 = the stricter (OpenAI) limit
        self.assertRegex(self.tool.api_name, pattern)


class MockProviderTests(SimpleTestCase):
    def test_pops_scripted_responses_in_order(self):
        p = MockLLMProvider([LLMResponse(text='first'), LLMResponse(text='second')])
        self.assertEqual(p.respond(messages=[]).text, 'first')
        self.assertEqual(p.respond(messages=[]).text, 'second')

    def test_echoes_user_when_exhausted(self):
        p = MockLLMProvider()
        out = p.respond(messages=[LLMMessage(role='user', content='hi there')])
        self.assertIn('hi there', out.text)

    def test_records_calls(self):
        p = MockLLMProvider([LLMResponse(text='x')])
        p.respond(messages=[LLMMessage(role='user', content='q')], tools=[])
        self.assertEqual(len(p.calls), 1)


class OpenAIArgParsingTests(SimpleTestCase):
    """Malformed tool-call JSON falls back to {} AND records a parse_error so the
    runtime can surface it back to the model (instead of silently invoking the
    tool with empty args).

    Built with object.__new__ to skip __init__ (no SDK key / network needed);
    we inject a fake client.
    """

    def _provider_with_args(self, raw_arguments: str) -> OpenAIProvider:
        p = OpenAIProvider.__new__(OpenAIProvider)
        p.model = 'gpt-4o-mini'
        fake_tc = SimpleNamespace(
            id='c1', function=SimpleNamespace(name='do', arguments=raw_arguments)
        )
        completion = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='', tool_calls=[fake_tc]))],
            usage=SimpleNamespace(prompt_tokens=5, completion_tokens=7),
        )
        p._client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: completion))
        )
        return p

    def test_valid_json_parsed(self):
        p = self._provider_with_args('{"x": 1}')
        resp = p.respond(messages=[LLMMessage(role='user', content='hi')])
        self.assertEqual(resp.tool_calls[0].arguments, {'x': 1})
        self.assertEqual(resp.tool_calls[0].parse_error, '')
        self.assertEqual(resp.prompt_tokens, 5)

    def test_malformed_json_falls_back_to_empty_and_records_error(self):
        p = self._provider_with_args('{not valid json')
        resp = p.respond(messages=[LLMMessage(role='user', content='hi')])
        self.assertEqual(resp.tool_calls[0].arguments, {})
        self.assertIn('malformed JSON', resp.tool_calls[0].parse_error)


class ProviderResolutionTests(SimpleTestCase):
    def test_unknown_provider_resolves_to_graceful_mock(self):
        provider = get_llm_provider('totally_unknown_provider')
        # Must not raise; responds with a degraded-but-valid message.
        out = provider.respond(messages=[LLMMessage(role='user', content='hi')])
        self.assertIsInstance(out, LLMResponse)
        self.assertIsInstance(out.text, str)

    def test_apikey_fun_is_a_registered_provider(self):
        # apikey.fun is offered in the AI-providers settings panel + the
        # ai_provider enum, so selecting it must resolve to a real provider
        # class — not the "No AI provider selected" unconfigured mock. With a
        # key configured (as in prod) it resolves to the apikey provider.
        from unittest.mock import patch

        from core.agents.llm import _PROVIDER_CLASSES, ApikeyProvider
        from core.agents.provider_registry import ProviderConfig

        self.assertIs(_PROVIDER_CLASSES.get('apikey'), ApikeyProvider)

        cfg = ProviderConfig(
            provider='apikey',
            api_key='sk-test',
            base_url='https://api.apikey.fun/v1',
            model='gpt-4o-mini',
            embedding_model='',
        )
        with patch('core.agents.provider_registry.get_provider_config', return_value=cfg):
            provider = get_llm_provider('apikey', use_fallback=False)
        self.assertEqual(provider.name, 'apikey')

    def test_deepseek_is_a_registered_provider(self):
        from unittest.mock import patch

        from core.agents.llm import _PROVIDER_CLASSES, DeepSeekProvider
        from core.agents.provider_registry import ProviderConfig

        self.assertIs(_PROVIDER_CLASSES.get('deepseek'), DeepSeekProvider)

        cfg = ProviderConfig(
            provider='deepseek',
            api_key='sk-test',
            base_url='https://api.deepseek.com',
            model='deepseek-chat',
            embedding_model='',
        )
        with patch('core.agents.provider_registry.get_provider_config', return_value=cfg):
            provider = get_llm_provider('deepseek', use_fallback=False)
        self.assertEqual(provider.name, 'deepseek')

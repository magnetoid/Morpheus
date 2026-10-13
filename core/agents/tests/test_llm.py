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

    def test_moonshot_is_a_registered_provider(self):
        # Moonshot (Kimi) is offered in the AI-providers panel + the ai_provider
        # enum; the class must exist and be selected (not the mock) when chosen —
        # the three-place-wiring landmine (config without a class → silent mock).
        from unittest.mock import patch

        from core.agents.llm import _PROVIDER_CLASSES, MoonshotProvider
        from core.agents.provider_registry import ProviderConfig

        self.assertIs(_PROVIDER_CLASSES.get('moonshot'), MoonshotProvider)

        cfg = ProviderConfig(
            provider='moonshot',
            api_key='sk-test',
            base_url='https://api.moonshot.ai/v1',
            model='kimi-latest',
            embedding_model='',
        )
        with patch('core.agents.provider_registry.get_provider_config', return_value=cfg):
            provider = get_llm_provider('moonshot', use_fallback=False)
        self.assertEqual(provider.name, 'moonshot')


class DegradedSentinelTests(SimpleTestCase):
    def test_is_degraded_response_truth_table(self):
        from core.agents.llm import is_degraded_response

        self.assertTrue(is_degraded_response('[All AI providers degraded. Last error: x]'))
        self.assertTrue(is_degraded_response('[Upstream AI provider is degraded — circuit open]'))
        self.assertTrue(is_degraded_response('  [All AI providers degraded...'))
        self.assertFalse(is_degraded_response('Here is your answer about degraded providers.'))
        self.assertFalse(is_degraded_response(''))
        self.assertFalse(is_degraded_response(None))


class FallbackRouterTests(SimpleTestCase):
    def _provider(self, name, *, raises=None, text='ok'):
        from core.agents.llm import LLMProvider

        class _P(LLMProvider):
            def respond(self, **_kw):
                if raises:
                    raise raises
                return LLMResponse(text=text, model='m')

        p = _P()
        p.name = name
        p.model = 'm'
        return p

    def test_failover_to_working_secondary(self):
        from core.agents.llm import FallbackProviderRouter

        router = FallbackProviderRouter(
            self._provider('primary', raises=RuntimeError('primary down')),
            [self._provider('secondary', text='rescued')],
        )
        resp = router.respond(messages=[], tools=[])
        self.assertEqual(resp.text, 'rescued')

    def test_sentinel_reports_primary_error_not_last_secondary(self):
        # Regression: prod showed "Could not resolve authentication method" —
        # an UNCONFIGURED secondary's auth noise — masking the primary's real
        # failure. The sentinel must carry the primary's error.
        from core.agents.llm import FallbackProviderRouter

        router = FallbackProviderRouter(
            self._provider('primary', raises=RuntimeError('primary: real cause')),
            [
                self._provider(
                    'anthropic', raises=RuntimeError('Could not resolve authentication method')
                )
            ],
        )
        resp = router.respond(messages=[], tools=[])
        self.assertIn('[All AI providers degraded', resp.text)
        self.assertIn('real cause', resp.text)
        self.assertNotIn('Could not resolve authentication', resp.text)

    def test_unconfigured_fallbacks_are_not_added_as_secondaries(self):
        # Regression: OpenAI/Anthropic SDK clients construct fine with NO key
        # (auth is deferred), so the old `hasattr(_client)` check admitted
        # unconfigured providers into the fallback chain.
        from unittest.mock import patch

        from core.agents.llm import FallbackProviderRouter
        from core.agents.provider_registry import ProviderConfig

        def _cfg(provider=None):
            # Primary (deepseek) has a key; every would-be fallback does not.
            key = 'sk-test' if provider == 'deepseek' else ''
            return ProviderConfig(
                provider=provider or 'deepseek',
                api_key=key,
                base_url='',
                model='deepseek-chat',
                embedding_model='',
            )

        with patch('core.agents.provider_registry.get_provider_config', side_effect=_cfg):
            provider = get_llm_provider('deepseek', use_fallback=True)
        self.assertNotIsInstance(provider, FallbackProviderRouter)
        self.assertEqual(provider.name, 'deepseek')

    def test_configured_fallback_is_added(self):
        from unittest.mock import patch

        from core.agents.llm import FallbackProviderRouter
        from core.agents.provider_registry import ProviderConfig

        def _cfg(provider=None):
            # Primary + anthropic configured; openai/gemini not.
            key = 'sk-test' if provider in ('deepseek', 'anthropic') else ''
            return ProviderConfig(
                provider=provider or 'deepseek',
                api_key=key,
                base_url='',
                model='m',
                embedding_model='',
            )

        with patch('core.agents.provider_registry.get_provider_config', side_effect=_cfg):
            provider = get_llm_provider('deepseek', use_fallback=True)
        self.assertIsInstance(provider, FallbackProviderRouter)
        self.assertEqual([s.name for s in provider.secondaries], ['anthropic'])


class ReasoningRetryTests(SimpleTestCase):
    """A reasoning model that spends its whole budget thinking returns HTTP 200
    with empty content and finish_reason='length'. Core read that as "nothing to
    say" and the Worker/briefing got an empty reply (the prod deepseek model). It
    now retries once with headroom. Mirrors ai_assistant's gateway fix.
    """

    def _completion(self, content, finish_reason='stop', reasoning_tokens=0, tool_calls=None):
        details = SimpleNamespace(reasoning_tokens=reasoning_tokens)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content, tool_calls=tool_calls or []),
                    finish_reason=finish_reason,
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=5,
                completion_tokens=reasoning_tokens or 7,
                completion_tokens_details=details,
            ),
        )

    def _provider(self, completions):
        p = OpenAIProvider.__new__(OpenAIProvider)
        p.model = 'deepseek-reasoner'
        calls = []

        def create(**kw):
            calls.append(kw)
            return completions[len(calls) - 1]

        p._client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )
        p._calls = calls
        return p

    def test_empty_reasoning_completion_is_retried_with_headroom(self):
        p = self._provider(
            [
                self._completion('', 'length', reasoning_tokens=1024),
                self._completion('The real answer.', 'stop', reasoning_tokens=800),
            ]
        )
        resp = p.respond(
            messages=[LLMMessage(role='user', content='reasoning-retry-a')], max_tokens=1024
        )
        self.assertEqual(resp.text, 'The real answer.')
        self.assertEqual(len(p._calls), 2)
        self.assertGreater(p._calls[1]['max_tokens'], p._calls[0]['max_tokens'])

    def test_a_tool_call_with_empty_text_is_not_a_reasoning_burn(self):
        tc = SimpleNamespace(id='c1', function=SimpleNamespace(name='do', arguments='{}'))
        p = self._provider([self._completion('', 'tool_calls', tool_calls=[tc])])
        resp = p.respond(messages=[LLMMessage(role='user', content='reasoning-retry-tool')])
        self.assertEqual(len(p._calls), 1)
        self.assertEqual(resp.tool_calls[0].name, 'do')

    def test_a_healthy_answer_is_not_retried(self):
        p = self._provider([self._completion('Done.', 'stop')])
        resp = p.respond(messages=[LLMMessage(role='user', content='reasoning-retry-healthy')])
        self.assertEqual((resp.text, len(p._calls)), ('Done.', 1))

    def test_two_empty_answers_do_not_loop(self):
        p = self._provider(
            [
                self._completion('', 'length', reasoning_tokens=1024),
                self._completion('', 'length', reasoning_tokens=8000),
            ]
        )
        resp = p.respond(
            messages=[LLMMessage(role='user', content='reasoning-retry-loop')], max_tokens=1024
        )
        self.assertEqual((resp.text, len(p._calls)), ('', 2))

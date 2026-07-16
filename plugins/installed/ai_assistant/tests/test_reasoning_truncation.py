"""A reasoning model must not silently return an empty completion.

Found live on dotbooks.store (deepseek-v4-pro): reasoning models bill their
hidden thinking against ``max_tokens``, so a budget sized for a non-reasoning
model — ``call_llm`` passes 600, the taxonomy copy generator passed 400 — is
consumed entirely by reasoning. The API then returns HTTP 200 with EMPTY
content and ``finish_reason='length'``, which every caller reads as "the model
had nothing to say". Dashboard AI generations silently produced nothing.

The gateway now recognises that exact shape and retries once with headroom.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase

from plugins.installed.ai_assistant.services.config import ProviderConfig
from plugins.installed.ai_assistant.services.llm import (
    _REASONING_MIN_TOKENS,
    OpenAIGateway,
    _truncated_while_reasoning,
)


def _response(content, finish_reason='stop', reasoning_tokens=0):
    """Mimic an OpenAI-compatible ChatCompletion."""
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason=finish_reason,
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=42,
            completion_tokens=reasoning_tokens or 10,
            completion_tokens_details=SimpleNamespace(reasoning_tokens=reasoning_tokens),
        ),
    )


class TruncationDetectionTests(TestCase):
    def test_detects_empty_content_burned_on_reasoning(self):
        self.assertTrue(_truncated_while_reasoning(_response('', 'length', reasoning_tokens=400)))

    def test_plain_length_truncation_is_not_a_reasoning_burn(self):
        """A non-reasoning model that ran out of room mid-sentence still
        returned prose — that's a different problem, not this retry's job."""
        self.assertFalse(_truncated_while_reasoning(_response('', 'length', reasoning_tokens=0)))

    def test_normal_completion_is_not_truncation(self):
        self.assertFalse(_truncated_while_reasoning(_response('{"description": "hi"}', 'stop')))

    def test_malformed_response_does_not_raise(self):
        self.assertFalse(_truncated_while_reasoning(SimpleNamespace()))
        self.assertFalse(_truncated_while_reasoning(None))


class ReasoningRetryTests(TestCase):
    def _gateway(self):
        with patch('core.agents.llm._openai_client', return_value=MagicMock()):
            return OpenAIGateway(
                ProviderConfig(
                    provider='deepseek',
                    api_key='k',
                    base_url='',
                    model='deepseek-v4-pro',
                    embedding_model='',
                )
            )

    @patch('plugins.installed.ai_assistant.services.llm.LLMGateway._log', MagicMock())
    def test_retries_with_headroom_and_returns_the_answer(self):
        gateway = self._gateway()
        create = gateway.client.chat.completions.create
        create.side_effect = [
            _response('', 'length', reasoning_tokens=400),  # burned thinking
            _response('{"description": "Real copy."}', 'stop', reasoning_tokens=790),
        ]
        result = gateway.complete('write copy', max_tokens=400)
        self.assertEqual(result, '{"description": "Real copy."}')
        self.assertEqual(create.call_count, 2)
        self.assertEqual(create.call_args_list[0].kwargs['max_tokens'], 400)
        self.assertGreaterEqual(
            create.call_args_list[1].kwargs['max_tokens'], _REASONING_MIN_TOKENS
        )

    @patch('plugins.installed.ai_assistant.services.llm.LLMGateway._log', MagicMock())
    def test_retries_at_most_once(self):
        """Two empty answers means something else is wrong — don't loop, and
        don't burn a third budget."""
        gateway = self._gateway()
        create = gateway.client.chat.completions.create
        create.side_effect = [
            _response('', 'length', reasoning_tokens=400),
            _response('', 'length', reasoning_tokens=4000),
        ]
        self.assertEqual(gateway.complete('write copy', max_tokens=400), '')
        self.assertEqual(create.call_count, 2)

    @patch('plugins.installed.ai_assistant.services.llm.LLMGateway._log', MagicMock())
    def test_healthy_completion_is_not_retried(self):
        gateway = self._gateway()
        create = gateway.client.chat.completions.create
        create.side_effect = [_response('{"description": "Fine."}', 'stop')]
        self.assertEqual(gateway.complete('write copy', max_tokens=400), '{"description": "Fine."}')
        self.assertEqual(create.call_count, 1)

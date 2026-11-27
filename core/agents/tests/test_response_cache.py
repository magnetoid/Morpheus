"""The breaker's response cache keeps only real answers, and a hit costs nothing.

An empty reply (a reasoning model that spent its tokens thinking) was kept for an
hour, so the same truncated answer came back for every retry; and a hit reported
the original call's tokens again, which the spend guard recorded a second time.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

from django.test import TestCase

from core.agents.llm import LLMMessage, LLMProvider, LLMResponse, _llm_breaker


class _Scripted(LLMProvider):
    model = 'gpt-4o'

    def __init__(self, *replies):
        self.name = f'cache-test-{uuid.uuid4().hex}'
        self.replies = list(replies)
        self.calls = 0

    @_llm_breaker
    def respond(self, *, messages, tools=None, temperature=0.3, max_tokens=1024):
        self.calls += 1
        return self.replies.pop(0)


def _ask(provider):
    return provider.respond(messages=[LLMMessage(role='user', content='same question')])


class ResponseCacheTests(TestCase):
    def test_an_empty_reply_is_not_kept(self):
        provider = _Scripted(
            LLMResponse(text='', prompt_tokens=9, completion_tokens=400),
            LLMResponse(text='The answer.', prompt_tokens=9, completion_tokens=3),
        )
        self.assertEqual(_ask(provider).text, '')
        self.assertEqual(_ask(provider).text, 'The answer.')
        self.assertEqual(provider.calls, 2)

    def test_a_hit_reports_no_tokens_and_the_guard_records_them_once(self):
        provider = _Scripted(LLMResponse(text='Cached.', prompt_tokens=10, completion_tokens=5))
        with patch('core.agents.guardrails.record_model_usage') as record:
            first = _ask(provider)
            second = _ask(provider)
        self.assertEqual(provider.calls, 1)
        self.assertEqual((first.prompt_tokens, first.completion_tokens), (10, 5))
        self.assertEqual(second.text, 'Cached.')
        self.assertEqual((second.prompt_tokens, second.completion_tokens), (0, 0))
        spent = [c.args[1:] for c in record.call_args_list if any(c.args[1:])]
        self.assertEqual(spent, [(10, 5)])

"""The daily briefing's run reaches the spend cap (v0.199.0).

The briefing runs the Worker with no `AgentRun` row. The runtime's own model
calls answer inside `run_scope()`, where the provider guard records nothing
because the run's row is expected to hold the tokens. With no row, a briefing
that read the whole store every morning cost nothing as far as the cap knew.
"""

from __future__ import annotations

import json

from django.test import TestCase

from core.agents import guardrails
from core.agents.llm import LLMResponse, MockLLMProvider
from core.agents.models import ModelUsageDay
from core.assistant.briefing import run_daily_briefing
from core.models import StoreSettings


class BriefingSpendTests(TestCase):
    def setUp(self):
        settings = StoreSettings.objects.first() or StoreSettings()
        settings.ai_daily_briefing = True
        settings.save()

    def _provider(self, **tokens):
        text = json.dumps({'briefing': 'A quiet day.', 'actions': []})
        provider = MockLLMProvider(responses=[LLMResponse(text=text, **tokens)], echo_user=False)
        provider.model = 'gpt-4o'
        return provider

    def test_the_briefings_tokens_are_counted_for_the_day(self):
        out = run_daily_briefing(
            provider=self._provider(prompt_tokens=900_000, completion_tokens=100)
        )

        self.assertEqual(out['status'], 'ok')
        day = ModelUsageDay.objects.get()
        self.assertEqual(
            (day.model, day.prompt_tokens, day.completion_tokens), ('gpt-4o', 900_000, 100)
        )
        self.assertGreater(guardrails.daily_spend_usd(), 2.0)

    def test_a_briefing_that_spent_nothing_writes_no_row(self):
        run_daily_briefing(provider=self._provider())
        self.assertFalse(ModelUsageDay.objects.exists())

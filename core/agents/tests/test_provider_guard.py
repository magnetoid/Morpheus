"""Every model call through a core provider obeys the merchant's guardrails.

Six callers reached `provider.respond()` directly — page help, the brain
analyst, the morning briefing, dynamics autopilot, self-improvement, the
dashboard's description fill — with the kill switch off and outside the spend
cap. The guard now sits on the provider class itself; calls made outside the
agent runtime's own loop are counted in ModelUsageDay so the cap sees them.
"""

from __future__ import annotations

from django.test import TestCase

from core.agents import guardrails
from core.agents.llm import FallbackProviderRouter, LLMResponse, LLMToolCall, MockLLMProvider
from core.agents.models import ModelUsageDay
from core.agents.runtime import AgentRuntime
from core.agents.tests.test_runtime import _agent, _tool


def _set(**kw):
    from plugins.registry import app_registry

    plugin = app_registry.get('agent_core')
    for k, v in kw.items():
        plugin.set_config(k, v)


def _resp(pt=0, ct=0, text='x'):
    return LLMResponse(text=text, prompt_tokens=pt, completion_tokens=ct, model='gpt-4o')


class GuardTests(TestCase):
    def setUp(self):
        self.addCleanup(_set, agents_paused=False, spend_cap_daily=0)

    def test_switched_off_ai_makes_no_call(self):
        _set(agents_paused=True)
        provider = MockLLMProvider([_resp()])
        with self.assertRaises(guardrails.AIPaused) as cm:
            provider.respond(messages=[])
        self.assertEqual(str(cm.exception), guardrails.PAUSED_MESSAGE)
        self.assertEqual(provider.calls, [])

    def test_a_reached_spend_cap_makes_no_call(self):
        _set(spend_cap_daily=1.0)
        ModelUsageDay.objects.create(
            day=guardrails.today_start().date(), model='gpt-4o', prompt_tokens=1_000_000
        )
        provider = MockLLMProvider([_resp()])
        with self.assertRaises(guardrails.AIPaused) as cm:
            provider.respond(messages=[])
        self.assertEqual(str(cm.exception), guardrails.CAP_MESSAGE)

    def test_the_ai_assistant_name_is_the_same_class(self):
        from plugins.installed.ai_assistant.services.llm import AIPaused

        self.assertIs(AIPaused, guardrails.AIPaused)


class UsageTests(TestCase):
    def _usage(self):
        return {
            (r.model, r.prompt_tokens, r.completion_tokens) for r in ModelUsageDay.objects.all()
        }

    def test_a_call_outside_a_run_is_counted(self):
        MockLLMProvider([_resp(100, 20), _resp(1, 2)]).respond(messages=[])
        self.assertEqual(self._usage(), {('gpt-4o', 100, 20)})

    def test_calls_accumulate_on_one_row(self):
        provider = MockLLMProvider([_resp(100, 20), _resp(1, 2)])
        provider.respond(messages=[])
        provider.respond(messages=[])
        self.assertEqual(self._usage(), {('gpt-4o', 101, 22)})

    def test_the_fallback_router_counts_its_call_once(self):
        router = FallbackProviderRouter(MockLLMProvider([_resp(50, 5)]), [])
        router.respond(messages=[])
        self.assertEqual(self._usage(), {('gpt-4o', 50, 5)})

    def test_counted_usage_reaches_the_spend_cap(self):
        MockLLMProvider([_resp(1_000_000, 0)]).respond(messages=[])
        self.assertGreater(guardrails.daily_spend_usd(), 2.0)

    def test_a_row_made_by_another_worker_is_added_to_not_lost(self):
        # Review Focus 2: the row already exists when this worker records.
        ModelUsageDay.objects.create(
            day=guardrails.today_start().date(), model='gpt-4o', prompt_tokens=10
        )
        guardrails.record_model_usage('gpt-4o', 5, 1)
        self.assertEqual(self._usage(), {('gpt-4o', 15, 1)})

    def test_a_runs_own_calls_are_not_counted_twice(self):
        agent = _agent(tools=[_tool()], max_steps=3)
        provider = MockLLMProvider([_resp(70, 7, text='done')])
        res = AgentRuntime(agent, provider=provider).run(user_message='go', context={})
        self.assertEqual(res.state, 'completed')
        self.assertEqual(ModelUsageDay.objects.count(), 0)

    def test_a_model_call_made_by_a_tool_inside_a_run_is_counted(self):
        def handler(**_):
            MockLLMProvider([_resp(9, 3)]).respond(messages=[])
            return {'ok': True}

        agent = _agent(tools=[_tool(handler=handler)], max_steps=3)
        provider = MockLLMProvider(
            [
                LLMResponse(tool_calls=[LLMToolCall(id='c', name='do_thing', arguments={})]),
                _resp(text='done'),
            ]
        )
        AgentRuntime(agent, provider=provider).run(user_message='go', context={})
        self.assertEqual(self._usage(), {('gpt-4o', 9, 3)})

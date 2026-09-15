"""Merchant agent guardrails — the core mechanism + kill switch + daily caps.

Everything is OFF by default (a bare run is unaffected). With the merchant knobs
set: the kill switch aborts a delegated run and makes Linda decline gracefully;
the daily run cap refuses a new run at start; the USD spend cap fires for priced
models but is a documented no-op for unpriced/self-hosted ones.

Money-tool caps (price %, refund) are tested in the plugins that enforce them
(catalog / orders), so this suite stays free of plugins.installed imports.
"""

from __future__ import annotations

from django.test import TestCase

from core.agents import guardrails
from core.agents.llm import LLMResponse, MockLLMProvider
from core.agents.models import AgentRun
from core.agents.runtime import AgentRuntime
from core.agents.tests.test_runtime import _agent, _tool


def _set_guardrail(**kw):
    """Persist guardrail config the way the settings panel does."""
    from plugins.registry import app_registry

    plugin = app_registry.get('agent_core')
    for k, v in kw.items():
        plugin.set_config(k, v)
    return plugin


def _run(agent_name='w', **kw):
    return AgentRun.objects.create(agent_name=agent_name, user_message='x', **kw)


class GuardrailConfigTests(TestCase):
    def test_all_off_by_default(self):
        self.assertFalse(guardrails.agents_paused())
        self.assertEqual(guardrails.max_agent_runs_daily(), 0)
        self.assertEqual(guardrails.daily_spend_cap_usd(), 0)
        self.assertEqual(guardrails.max_price_change_pct(), 0)
        self.assertEqual(guardrails.max_refund_value(), 0)
        self.assertIsNone(guardrails.run_start_block_reason())

    def test_agents_paused_reads_config_fresh(self):
        # A fresh read every time (invalidate → DB) is what lets a worker see a
        # switch flipped from the web dashboard.
        self.assertFalse(guardrails.agents_paused())
        _set_guardrail(agents_paused=True)
        self.assertTrue(guardrails.agents_paused())
        _set_guardrail(agents_paused=False)
        self.assertFalse(guardrails.agents_paused())

    def test_bad_numeric_config_is_treated_as_no_cap(self):
        _set_guardrail(spend_cap_daily='not-a-number', max_agent_runs_daily=-5)
        self.assertEqual(guardrails.daily_spend_cap_usd(), 0)
        self.assertEqual(guardrails.max_agent_runs_daily(), 0)


class DailyRunCapTests(TestCase):
    def test_run_cap_blocks_a_new_run(self):
        _set_guardrail(max_agent_runs_daily=2)
        _run(state='completed')
        _run(state='completed')
        self.assertEqual(guardrails.run_start_block_reason(), 'run_cap_exceeded')

    def test_run_cap_excludes_the_current_run(self):
        _set_guardrail(max_agent_runs_daily=1)
        r = _run(state='running')
        # Excluding the run's own row there are 0 others → allowed.
        self.assertIsNone(guardrails.run_start_block_reason(exclude_id=r.id))
        # Counting it → already at the cap.
        self.assertEqual(guardrails.run_start_block_reason(), 'run_cap_exceeded')


class DailySpendCapTests(TestCase):
    def test_spend_cap_blocks_a_priced_model(self):
        _set_guardrail(spend_cap_daily=1.0)
        # gpt-4o input is $2.50 / 1M tokens → 1M prompt tokens ≈ $2.50 > $1.
        _run(state='completed', model='gpt-4o', prompt_tokens=1_000_000)
        self.assertEqual(guardrails.run_start_block_reason(), 'spend_cap_exceeded')

    def test_spend_cap_blocks_the_production_model(self):
        # deepseek-v4-pro used to be absent from the price table, so it estimated
        # $0.00 and the merchant's USD cap could never trip on prod — the
        # advertised guardrail was inert exactly where it mattered. Now priced.
        _set_guardrail(spend_cap_daily=1.0)
        _run(state='completed', model='deepseek-v4-pro', prompt_tokens=5_000_000)
        self.assertEqual(guardrails.run_start_block_reason(), 'spend_cap_exceeded')

    def test_spend_cap_is_still_a_noop_for_a_genuinely_unpriced_model(self):
        # The structural caveat remains for any model absent from _PRICES: the
        # run-count cap, not the USD cap, is the hard limit there.
        _set_guardrail(spend_cap_daily=1.0)
        _run(state='completed', model='some-unlisted-model', prompt_tokens=5_000_000)
        self.assertIsNone(guardrails.run_start_block_reason())


class KillSwitchRuntimeTests(TestCase):
    def test_paused_aborts_before_any_provider_call(self):
        _set_guardrail(agents_paused=True)
        agent = _agent(tools=[_tool()], max_steps=4)
        provider = MockLLMProvider([LLMResponse(text='should not run')])
        res = AgentRuntime(agent, provider=provider).run(user_message='go', context={})
        self.assertEqual(res.state, 'failed')
        self.assertEqual(res.error, 'agents_paused')
        self.assertEqual(provider.calls, [])

    def test_run_cap_aborts_before_any_provider_call(self):
        _set_guardrail(max_agent_runs_daily=1)
        _run(state='completed')  # one run already today
        agent = _agent(tools=[_tool()], max_steps=4)
        provider = MockLLMProvider([LLMResponse(text='nope')])
        res = AgentRuntime(agent, provider=provider).run(user_message='go', context={})
        self.assertEqual(res.state, 'failed')
        self.assertEqual(res.error, 'run_cap_exceeded')
        self.assertEqual(provider.calls, [])

    def test_runs_normally_with_guardrails_off(self):
        agent = _agent(tools=[_tool()], max_steps=4)
        provider = MockLLMProvider([LLMResponse(text='done')])
        res = AgentRuntime(agent, provider=provider).run(user_message='go', context={})
        self.assertEqual(res.state, 'completed')
        self.assertEqual(res.text, 'done')


class KillSwitchLindaTests(TestCase):
    def test_linda_declines_gracefully_when_paused(self):
        _set_guardrail(agents_paused=True)
        from unittest import mock

        from core.assistant.runtime import Assistant

        with mock.patch(
            'core.assistant.janus_engine.iter_janus_turn',
            side_effect=AssertionError('engine started while agents are paused'),
        ):
            events = list(Assistant().stream(message='hi', conversation_key='t:paused'))
        res = events[-1]['result']
        # Graceful decline — a completed turn with a friendly line, never a
        # failure (a deliberate pause is not an outage) and never an engine run.
        self.assertEqual(res.state, 'completed')
        self.assertIn('paused', res.text.lower())

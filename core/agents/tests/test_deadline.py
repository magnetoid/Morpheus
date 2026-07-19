"""Cooperative runtime deadline stops a timed-out run (deep-debug #6).

``agent_core._run_with_timeout`` runs the loop on a daemon thread and raises
``TimeoutError`` when ``join()`` expires — but Python can't kill the thread, so
without a cooperative check it kept driving the LLM and executing (writing)
tools for every remaining step, long after the caller reported the run failed.
The loop now polls a monotonic ``context['deadline']`` before each provider call
and each tool dispatch, so a timed-out run stops issuing new LLM/tool calls.
"""

from __future__ import annotations

import time

from django.test import TestCase

from core.agents.llm import LLMResponse, LLMToolCall, MockLLMProvider
from core.agents.runtime import AgentRuntime
from core.agents.tests.test_runtime import _agent, _AlwaysToolProvider, _tool


class RuntimeDeadlineTests(TestCase):
    def test_past_deadline_aborts_before_any_provider_or_tool_call(self):
        calls = []
        tool = _tool(handler=lambda **kw: calls.append(1) or {'ok': True})
        agent = _agent(tools=[tool], max_steps=8)
        # A provider that would loop forever calling the tool — only the deadline
        # can stop it.
        res = AgentRuntime(agent, provider=_AlwaysToolProvider()).run(
            user_message='go',
            context={'deadline': time.monotonic() - 1},  # already expired
        )
        self.assertEqual(res.state, 'failed')
        self.assertEqual(res.error, 'deadline_exceeded')
        self.assertEqual(calls, [])  # the write-tool was never executed

    def test_future_deadline_does_not_interfere_with_a_normal_run(self):
        calls = []
        tool = _tool(handler=lambda **kw: calls.append(1) or {'ok': True})
        agent = _agent(tools=[tool], max_steps=8)
        provider = MockLLMProvider(
            [
                LLMResponse(tool_calls=[LLMToolCall(id='c1', name='do_thing', arguments={})]),
                LLMResponse(text='done'),
            ]
        )
        res = AgentRuntime(agent, provider=provider).run(
            user_message='go',
            context={'deadline': time.monotonic() + 100},  # far in the future
        )
        self.assertEqual(res.state, 'completed')
        self.assertEqual(res.text, 'done')
        self.assertEqual(calls, [1])  # ran normally — one tool call, one final

    def test_no_deadline_key_runs_normally(self):
        agent = _agent(tools=[_tool()], max_steps=8)
        provider = MockLLMProvider([LLMResponse(text='hi')])
        res = AgentRuntime(agent, provider=provider).run(user_message='go', context={})
        self.assertEqual(res.state, 'completed')

"""What a run spends is counted, and a tool is known by one name (v0.199.0).

- The summary call of context compaction answered inside the run and its
  tokens went nowhere: not on the trace, not on the run, not to the spend cap.
- A run answered by the fallback router's secondary was priced as the model
  the store chose.
- After the tool lookup the runtime kept the model's spelling of the name
  (``catalog__rename`` for ``catalog.rename``) for the trace, the audit trail,
  the usage counts and the approval request, so an approval recorded under one
  spelling was looked up under the other and never matched.
- A run was counted against the daily run cap by its own row whenever its
  caller did not put that row in the context (a spawned Worker).
"""

from __future__ import annotations

from unittest import mock

from django.test import TestCase

from core.agents import guardrails
from core.agents import runtime as runtime_module
from core.agents.base import MorpheusAgent
from core.agents.events import AgentEvents
from core.agents.llm import LLMResponse, LLMToolCall, MockLLMProvider
from core.agents.models import AgentRun
from core.agents.runtime import AgentRuntime
from core.agents.tools import Tool
from core.agents.usage import RunUsage


def _agent(*tools, requires_approval=False):
    # A bare instance, never a subclass (the pre-commit hook refuses those).
    agent = MorpheusAgent()
    agent.name = 'tester'
    agent.scopes = ['catalog.write']
    agent.max_steps = 4
    agent.requires_approval = requires_approval
    agent.get_tools = lambda: list(tools)
    return agent


def _rename_tool(**extra):
    return Tool(
        name='catalog.rename',
        description='d',
        handler=lambda **kw: {'ok': True},
        scopes=['catalog.write'],
        **extra,
    )


def _summarising(messages, *, summarizer=None, **_kw):
    summarizer('the earlier turns')
    return messages


class CompactionSpendTests(TestCase):
    def test_the_summary_call_is_counted(self):
        provider = MockLLMProvider(
            [
                LLMResponse(text='summary', prompt_tokens=40, completion_tokens=8),
                LLMResponse(text='done', prompt_tokens=10, completion_tokens=5),
            ]
        )
        usage = RunUsage()

        with mock.patch.object(runtime_module, 'compact', side_effect=_summarising):
            result = AgentRuntime(_agent(), provider=provider).run(user_message='go', usage=usage)

        self.assertEqual(result.state, 'completed')
        self.assertEqual(result.trace.prompt_tokens, 50)
        self.assertEqual(result.trace.completion_tokens, 13)
        self.assertEqual(usage.by_model(), {'mock-1': (50, 13)})


class AnsweringModelTests(TestCase):
    def test_usage_is_kept_under_the_model_that_answered(self):
        provider = MockLLMProvider(
            [
                LLMResponse(
                    tool_calls=[LLMToolCall(id='1', name='catalog.rename', arguments={})],
                    prompt_tokens=10,
                    completion_tokens=5,
                ),
                LLMResponse(
                    text='done', prompt_tokens=20, completion_tokens=7, model='claude-opus-4'
                ),
            ]
        )
        usage = RunUsage()

        AgentRuntime(_agent(_rename_tool()), provider=provider).run(user_message='go', usage=usage)

        self.assertEqual(usage.by_model(), {'mock-1': (10, 5), 'claude-opus-4': (20, 7)})
        self.assertEqual((usage.prompt_tokens, usage.completion_tokens), (30, 12))

    def test_a_run_works_without_a_meter(self):
        provider = MockLLMProvider([LLMResponse(text='hi', prompt_tokens=3, completion_tokens=2)])
        result = AgentRuntime(_agent(), provider=provider).run(user_message='go')
        self.assertEqual(result.trace.total_tokens(), 5)


class OneToolNameTests(TestCase):
    """The model may answer with the provider-safe spelling; everything the
    store records uses the tool's own name."""

    def _run(self, tool, **runtime_kw):
        provider = MockLLMProvider(
            [
                LLMResponse(
                    tool_calls=[LLMToolCall(id='c1', name='catalog__rename', arguments={'a': 1})]
                ),
                LLMResponse(text='done'),
            ]
        )
        hooks = runtime_module.hook_registry
        with (
            mock.patch.object(hooks, 'fire') as fire,
            mock.patch.object(hooks, 'filter', wraps=hooks.filter) as filtered,
        ):
            result = AgentRuntime(_agent(tool), provider=provider, **runtime_kw).run(
                user_message='go'
            )
        return result, provider, fire, filtered

    @staticmethod
    def _fired(fire, event):
        return [c.kwargs for c in fire.call_args_list if c.args and c.args[0] == event]

    def test_the_trace_and_the_events_carry_the_tools_own_name(self):
        result, provider, fire, filtered = self._run(_rename_tool())

        steps = [s for s in result.trace.steps if s.kind in ('tool_call', 'tool_result')]
        self.assertEqual([s.name for s in steps], ['catalog.rename', 'catalog.rename'])
        self.assertEqual(self._fired(fire, AgentEvents.TOOL_CALLED)[0]['tool'], 'catalog.rename')
        self.assertEqual(
            self._fired(filtered, AgentEvents.TOOL_CALLING)[0]['tool'], 'catalog.rename'
        )
        # The model gets its own spelling back, with the id it sent.
        back = [m for m in provider.calls[1]['messages'] if m.role == 'tool'][0]
        self.assertEqual((back.name, back.tool_call_id), ('catalog__rename', 'c1'))

    def test_an_approval_request_names_the_tool_the_resolver_looks_up(self):
        result, _provider, fire, _filtered = self._run(_rename_tool(requires_approval=True))

        asked = self._fired(fire, AgentEvents.STEP_APPROVAL_REQUIRED)
        self.assertEqual([k['tool'] for k in asked], ['catalog.rename'])
        refused = [s for s in result.trace.steps if s.kind == 'tool_call']
        self.assertEqual(refused[0].name, 'catalog.rename')

    def test_a_refusal_by_the_callers_own_check_names_it_too(self):
        _result, _provider, fire, _filtered = self._run(
            _rename_tool(requires_approval=True), approval_check=lambda tool, args: False
        )
        self.assertEqual(
            [k['tool'] for k in self._fired(fire, AgentEvents.STEP_REJECTED)], ['catalog.rename']
        )

    def test_a_failing_tool_is_reported_under_its_own_name(self):
        from core.agents.tools import ToolError

        def boom(**_kw):
            raise ToolError('nope')

        tool = Tool(name='catalog.rename', description='d', handler=boom, scopes=['catalog.write'])
        result, _provider, fire, _filtered = self._run(tool)

        self.assertEqual(self._fired(fire, AgentEvents.TOOL_FAILED)[0]['tool'], 'catalog.rename')
        failed = [s for s in result.trace.steps if s.kind == 'tool_result']
        self.assertEqual(failed[0].name, 'catalog.rename')

    def test_an_unknown_tool_keeps_the_name_the_model_sent(self):
        provider = MockLLMProvider(
            [
                LLMResponse(tool_calls=[LLMToolCall(id='c1', name='nope__tool', arguments={})]),
                LLMResponse(text='done'),
            ]
        )
        result = AgentRuntime(_agent(), provider=provider).run(user_message='go')
        self.assertEqual(
            [s.name for s in result.trace.steps if s.kind == 'tool_result'], ['nope__tool']
        )


class RunCapOwnRowTests(TestCase):
    def test_a_run_is_not_counted_against_the_cap_by_its_own_row(self):
        AgentRun.objects.create(agent_name='worker', state='completed')
        own = AgentRun.objects.create(agent_name='worker', state='running')
        provider = MockLLMProvider([LLMResponse(text='done')])

        with mock.patch.object(guardrails, 'max_agent_runs_daily', return_value=2):
            # No `agent_run` in the context: a spawned Worker passes only the id.
            result = AgentRuntime(_agent(), provider=provider).run(
                user_message='go', run_id=str(own.pk)
            )

        self.assertEqual(result.state, 'completed')

    def test_the_cap_still_refuses_once_other_runs_fill_it(self):
        AgentRun.objects.create(agent_name='worker', state='completed')
        AgentRun.objects.create(agent_name='worker', state='completed')
        own = AgentRun.objects.create(agent_name='worker', state='running')

        with mock.patch.object(guardrails, 'max_agent_runs_daily', return_value=2):
            result = AgentRuntime(_agent(), provider=MockLLMProvider([])).run(
                user_message='go', run_id=str(own.pk)
            )

        self.assertEqual((result.state, result.error), ('failed', 'run_cap_exceeded'))

    def test_a_run_id_that_is_no_row_key_changes_nothing(self):
        # A caller may name its run anything; only a row's key can be left out.
        AgentRun.objects.create(agent_name='worker', state='completed')
        provider = MockLLMProvider([LLMResponse(text='done')])

        with mock.patch.object(guardrails, 'max_agent_runs_daily', return_value=2):
            result = AgentRuntime(_agent(), provider=provider).run(
                user_message='go', run_id='briefing-2026-11-27'
            )

        self.assertEqual(result.state, 'completed')

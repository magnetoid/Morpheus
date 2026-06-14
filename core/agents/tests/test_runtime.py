"""AgentRuntime.run() — the tool-use loop.

These lock the kernel's most load-bearing, previously-untested code path:
final-answer, tool dispatch, error recovery (`_tool_back`), scope denial,
approval rejection, provider failure, and the max_steps guard. All driven by
MockLLMProvider — no network, no DB.
"""

from __future__ import annotations

from django.test import TestCase

from core.agents.base import MorpheusAgent
from core.agents.llm import LLMProvider, LLMResponse, LLMToolCall, MockLLMProvider
from core.agents.tools import Tool, ToolError, ToolResult


def _agent(*, scopes=None, tools=(), max_steps=8, requires_approval=False):
    """A bare MorpheusAgent instance (NOT a subclass — the pre-commit hook
    blocks new MorpheusAgent subclasses). `get_tools` is shadowed so the test
    is hermetic against the platform tool registry."""
    a = MorpheusAgent()
    a.name = 'tester'
    a.label = 'Tester'
    a.scopes = list(scopes or [])
    a.max_steps = max_steps
    a.requires_approval = requires_approval
    a.get_tools = lambda: list(tools)
    return a


def _tool(name='do_thing', *, scopes=None, requires_approval=False, handler=None):
    return Tool(
        name=name,
        description='d',
        handler=handler or (lambda **kw: {'ok': True}),
        scopes=list(scopes or []),
        requires_approval=requires_approval,
    )


class _AlwaysToolProvider(LLMProvider):
    name = 'loop'

    def respond(self, **_kw):
        return LLMResponse(tool_calls=[LLMToolCall(id='c', name='do_thing', arguments={})])


class _BoomProvider(LLMProvider):
    name = 'boom'

    def respond(self, **_kw):
        raise RuntimeError('429 rate limit exceeded')


class AgentRuntimeTests(TestCase):
    def _run(self, agent, provider, **kw):
        from core.agents.runtime import AgentRuntime

        return AgentRuntime(agent, provider=provider, **kw).run(user_message='go')

    def test_final_answer_no_tools(self):
        provider = MockLLMProvider(
            [LLMResponse(text='hello', prompt_tokens=10, completion_tokens=5)]
        )
        res = self._run(_agent(), provider)
        self.assertEqual(res.state, 'completed')
        self.assertEqual(res.text, 'hello')
        self.assertEqual(res.tool_calls, 0)
        self.assertEqual(res.trace.total_tokens(), 15)

    def test_tool_dispatch_then_final(self):
        called = []

        def handler(x=None, **kw):
            # tool.invoke only forwards arguments that are NAMED parameters, so
            # `x` must be declared to be received.
            called.append(x)
            return {'done': 1}

        tool = _tool(handler=handler)
        provider = MockLLMProvider(
            [
                LLMResponse(tool_calls=[LLMToolCall(id='c1', name='do_thing', arguments={'x': 1})]),
                LLMResponse(text='finished'),
            ]
        )
        res = self._run(_agent(tools=[tool]), provider)
        self.assertEqual(res.state, 'completed')
        self.assertEqual(res.text, 'finished')
        self.assertEqual(res.tool_calls, 1)
        self.assertEqual(called, [1])  # handler ran with the forwarded arg

    def test_unknown_tool_recovers(self):
        provider = MockLLMProvider(
            [
                LLMResponse(tool_calls=[LLMToolCall(id='c1', name='nope', arguments={})]),
                LLMResponse(text='recovered'),
            ]
        )
        res = self._run(_agent(), provider)
        self.assertEqual(res.state, 'completed')  # error fed back, not a crash
        self.assertEqual(res.text, 'recovered')
        errs = [s for s in res.trace.steps if s.metadata.get('failed')]
        self.assertTrue(errs and 'Unknown tool' in errs[0].content)

    def test_scope_denied_feeds_error_not_crash(self):
        tool = _tool(scopes=['catalog.write'])  # agent only holds catalog.read
        provider = MockLLMProvider(
            [
                LLMResponse(tool_calls=[LLMToolCall(id='c1', name='do_thing', arguments={})]),
                LLMResponse(text='ok'),
            ]
        )
        res = self._run(_agent(scopes=['catalog.read'], tools=[tool]), provider)
        self.assertEqual(res.state, 'completed')
        failed = [s for s in res.trace.steps if s.metadata.get('failed')]
        self.assertTrue(any('scope' in s.content.lower() for s in failed))

    def test_tool_error_recovers(self):
        def boom(**_kw):
            raise ToolError('boom inside tool')

        provider = MockLLMProvider(
            [
                LLMResponse(tool_calls=[LLMToolCall(id='c1', name='do_thing', arguments={})]),
                LLMResponse(text='handled'),
            ]
        )
        res = self._run(_agent(tools=[_tool(handler=boom)]), provider)
        self.assertEqual(res.state, 'completed')
        self.assertEqual(res.text, 'handled')

    def test_approval_rejected_skips_tool(self):
        called = []
        tool = _tool(requires_approval=True, handler=lambda **kw: called.append(1))
        provider = MockLLMProvider(
            [
                LLMResponse(tool_calls=[LLMToolCall(id='c1', name='do_thing', arguments={})]),
                LLMResponse(text='after rejection'),
            ]
        )
        res = self._run(_agent(tools=[tool]), provider, approval_check=lambda t, a: False)
        self.assertEqual(res.state, 'completed')
        self.assertEqual(called, [])  # handler never ran
        rejected = [s for s in res.trace.steps if s.metadata.get('rejected')]
        self.assertTrue(rejected)

    def test_approval_granted_runs_tool(self):
        called = []
        tool = _tool(requires_approval=True, handler=lambda **kw: called.append(1) or {'ok': 1})
        provider = MockLLMProvider(
            [
                LLMResponse(tool_calls=[LLMToolCall(id='c1', name='do_thing', arguments={})]),
                LLMResponse(text='done'),
            ]
        )
        res = self._run(_agent(tools=[tool]), provider, approval_check=lambda t, a: True)
        self.assertEqual(res.state, 'completed')
        self.assertEqual(called, [1])

    def test_provider_failure_aborts(self):
        res = self._run(_agent(), _BoomProvider())
        self.assertEqual(res.state, 'failed')
        self.assertIn('rate-limited', res.error.lower())

    def test_max_steps_exceeded(self):
        agent = _agent(tools=[_tool()], max_steps=2)
        res = self._run(agent, _AlwaysToolProvider())
        self.assertEqual(res.state, 'failed')
        self.assertEqual(res.error, 'max_steps_exceeded')

    def test_token_budget_exceeded_aborts(self):
        agent = _agent(tools=[_tool()], max_steps=8)
        agent.token_budget = 10
        # First response burns 20 tokens (over the cap) and asks for a tool, so
        # the loop continues; the next iteration's budget check aborts the run.
        provider = MockLLMProvider(
            [
                LLMResponse(
                    tool_calls=[LLMToolCall(id='c1', name='do_thing', arguments={})],
                    prompt_tokens=20,
                ),
                LLMResponse(text='should-not-reach'),
            ]
        )
        res = self._run(agent, provider)
        self.assertEqual(res.state, 'failed')
        self.assertEqual(res.error, 'budget_exceeded')

    def test_zero_budget_is_unlimited(self):
        agent = _agent(max_steps=8)  # token_budget defaults to 0
        provider = MockLLMProvider([LLMResponse(text='ok', prompt_tokens=9999)])
        res = self._run(agent, provider)
        self.assertEqual(res.state, 'completed')

    def test_returns_tool_result_object(self):
        tool = _tool(handler=lambda **kw: ToolResult(output={'n': 7}, display='seven'))
        provider = MockLLMProvider(
            [
                LLMResponse(tool_calls=[LLMToolCall(id='c1', name='do_thing', arguments={})]),
                LLMResponse(text='ok'),
            ]
        )
        res = self._run(_agent(tools=[tool]), provider)
        results = [s for s in res.trace.steps if s.kind == 'tool_result']
        self.assertEqual(results[-1].output, {'n': 7})
        self.assertEqual(results[-1].content, 'seven')

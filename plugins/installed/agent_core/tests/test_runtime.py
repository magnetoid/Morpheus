"""End-to-end tests for the agent runtime + tool dispatch."""

from __future__ import annotations

import sys

from django.test import TestCase

from core.agents import (
    AgentRuntime,
    LLMResponse,
    LLMToolCall,
    MockLLMProvider,
    MorpheusAgent,
    ToolError,
    ToolResult,
    agent_registry,
    tool,
)

_IS_SQLITE = 'sqlite' in (
    sys.modules.get('django.conf').settings.DATABASES['default']['ENGINE']
    if 'django.conf' in sys.modules
    else ''
)


# ─────────────────────────────────────────────────────────────────────────────
# Tools used by tests
# ─────────────────────────────────────────────────────────────────────────────


@tool(
    name='test.echo',
    description='Echo a string back.',
    scopes=['demo.read'],
    schema={'type': 'object', 'properties': {'text': {'type': 'string'}}, 'required': ['text']},
)
def _echo(*, text: str) -> ToolResult:
    return ToolResult(output={'echo': text})


@tool(
    name='test.boom',
    description='Always raises.',
    scopes=['demo.read'],
)
def _boom() -> ToolResult:
    raise ToolError('intentional')


class _DemoAgent(MorpheusAgent):
    name = 'demo_agent'
    label = 'Demo'
    description = 'Test agent.'
    audience = 'system'
    scopes = ['demo.read']
    default_tools = [_echo, _boom]
    max_steps = 4


class RuntimeFinalAnswerTests(TestCase):
    def test_runtime_returns_final_text_without_tools(self):
        provider = MockLLMProvider([LLMResponse(text='hello world')])
        runtime = AgentRuntime(_DemoAgent(), provider=provider)
        result = runtime.run(user_message='hi')
        self.assertEqual(result.state, 'completed')
        self.assertEqual(result.text, 'hello world')
        self.assertEqual(result.tool_calls, 0)

    def test_runtime_dispatches_tool_then_finalises(self):
        provider = MockLLMProvider(
            [
                LLMResponse(
                    tool_calls=[LLMToolCall(id='1', name='test.echo', arguments={'text': 'pong'})]
                ),
                LLMResponse(text='echoed'),
            ]
        )
        runtime = AgentRuntime(_DemoAgent(), provider=provider)
        result = runtime.run(user_message='ping')
        self.assertEqual(result.state, 'completed')
        self.assertEqual(result.tool_calls, 1)
        self.assertEqual(result.text, 'echoed')
        kinds = [s.kind for s in result.trace.steps]
        self.assertIn('tool_call', kinds)
        self.assertIn('tool_result', kinds)

    def test_tool_error_is_returned_to_llm(self):
        provider = MockLLMProvider(
            [
                LLMResponse(tool_calls=[LLMToolCall(id='1', name='test.boom', arguments={})]),
                LLMResponse(text='recovered'),
            ]
        )
        runtime = AgentRuntime(_DemoAgent(), provider=provider)
        result = runtime.run(user_message='hi')
        self.assertEqual(result.state, 'completed')
        # The LLM saw the error result and recovered.
        self.assertEqual(result.text, 'recovered')
        # The trace records the failed tool result.
        failed = [s for s in result.trace.steps if s.metadata.get('failed')]
        self.assertEqual(len(failed), 1)

    def test_unknown_tool_does_not_crash(self):
        provider = MockLLMProvider(
            [
                LLMResponse(tool_calls=[LLMToolCall(id='1', name='test.nope', arguments={})]),
                LLMResponse(text='moving on'),
            ]
        )
        runtime = AgentRuntime(_DemoAgent(), provider=provider)
        result = runtime.run(user_message='hi')
        self.assertEqual(result.state, 'completed')

    def test_max_steps_exceeded(self):
        # Loop returning only tool calls until cap fires.
        provider = MockLLMProvider(
            [
                LLMResponse(
                    tool_calls=[LLMToolCall(id=str(i), name='test.echo', arguments={'text': 'x'})]
                )
                for i in range(10)
            ]
        )
        agent = _DemoAgent()
        agent.max_steps = 2
        runtime = AgentRuntime(agent, provider=provider)
        result = runtime.run(user_message='hi')
        self.assertEqual(result.state, 'failed')
        self.assertIn('max_steps', result.error)


class ScopeEnforcementTests(TestCase):
    def test_tool_outside_scopes_is_rejected(self):
        @tool(name='test.priv', description='Admin only', scopes=['admin.write'])
        def _priv() -> ToolResult:  # pragma: no cover — should never run
            return ToolResult(output={'ok': True})

        class _Limited(MorpheusAgent):
            name = 'limited_agent'
            label = 'Limited'
            audience = 'system'
            scopes = ['demo.read']
            default_tools = [_priv]

        provider = MockLLMProvider(
            [
                LLMResponse(tool_calls=[LLMToolCall(id='1', name='test.priv', arguments={})]),
                LLMResponse(text='done'),
            ]
        )
        runtime = AgentRuntime(_Limited(), provider=provider)
        result = runtime.run(user_message='try')
        self.assertEqual(result.state, 'completed')
        # The trace shows the tool result was an error, not a successful invocation.
        results = [s for s in result.trace.steps if s.kind == 'tool_result']
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].metadata.get('failed'))


class RegistryTests(TestCase):
    def test_register_and_lookup(self):
        agent_registry.register_tool(_echo, plugin='__test')
        try:
            self.assertIs(agent_registry.get_tool('test.echo'), _echo)
            self.assertIn(_echo, agent_registry.tools_for_scopes(['demo.read']))
            self.assertNotIn(_echo, agent_registry.tools_for_scopes([]))
        finally:
            agent_registry.drop_plugin('__test')

"""Tests for the run/step persistence layer."""

from __future__ import annotations

from django.test import TestCase

from core.agents import (
    LLMResponse,
    LLMToolCall,
    MockLLMProvider,
    MorpheusAgent,
    ToolResult,
    agent_registry,
    tool,
)


@tool(
    name='persist_test.ping',
    description='Returns pong.',
    scopes=['t.read'],
)
def _ping() -> ToolResult:
    return ToolResult(output={'reply': 'pong'})


class _PersistAgent(MorpheusAgent):
    name = 'persist_agent'
    label = 'Persist Agent'
    audience = 'system'
    scopes = ['t.read']
    default_tools = [_ping]
    max_steps = 4


class RunPersistenceTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        agent_registry.register_agent(_PersistAgent(), plugin='__test_persist')

    @classmethod
    def tearDownClass(cls):
        agent_registry.drop_plugin('__test_persist')
        super().tearDownClass()

    def test_run_and_steps_are_persisted(self):
        # Inject the mock provider via monkeypatch on get_llm_provider.
        import plugins.installed.agent_core.services as svc
        from plugins.installed.agent_core.models import AgentRun, AgentStep
        from plugins.installed.agent_core.services import run_agent

        provider = MockLLMProvider(
            [
                LLMResponse(
                    tool_calls=[LLMToolCall(id='1', name='persist_test.ping', arguments={})]
                ),
                LLMResponse(text='all good'),
            ]
        )
        original = svc.get_llm_provider
        svc.get_llm_provider = lambda *a, **kw: provider
        try:
            result = run_agent(
                agent_name='persist_agent',
                user_message='go',
            )
        finally:
            svc.get_llm_provider = original

        self.assertEqual(result.state, 'completed')
        self.assertEqual(result.text, 'all good')

        run = AgentRun.objects.get(id=result.run_id)
        self.assertEqual(run.state, 'completed')
        self.assertEqual(run.tool_call_count, 1)
        self.assertEqual(run.final_text, 'all good')
        steps = list(AgentStep.objects.filter(run=run).order_by('seq'))
        kinds = [s.kind for s in steps]
        self.assertIn('user', kinds)
        self.assertIn('tool_call', kinds)
        self.assertIn('tool_result', kinds)
        self.assertIn('final', kinds)

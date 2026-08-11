"""Linda agentic-core hardening (2026-07).

Locks four fixes:
  * run_python's sandbox is READ-ONLY for real — mutating tools that were
    mislabeled `system.read` (memory.remember/forget, skills.record_outcome)
    are no longer script-callable;
  * the bridge's defence-in-depth scope re-check no longer dead-letters
    every scoped read tool for Linda (who has no `.scopes` attribute);
  * write-tool invocations land in core.audit (`assistant.tool_write`);
  * the legacy MCP shim requires a staff session.
"""

from __future__ import annotations

from django.test import Client, TestCase

from core.agents.llm import LLMResponse, LLMToolCall
from core.agents.tools import Tool
from core.assistant import Assistant


class SandboxReadOnlyTests(TestCase):
    def test_mutating_tools_are_not_script_callable(self):
        from core.assistant.tools.code import _available_tools

        names = set(_available_tools(None).keys())
        for mutating in ('memory.remember', 'memory.forget', 'skills.record_outcome'):
            self.assertNotIn(mutating, names)
        # Genuine reads stay available.
        self.assertIn('memory.recall', names)
        self.assertIn('skills.list', names)

    def test_scoped_read_tool_callable_when_agent_has_no_scope_model(self):
        # Regression: `agent_scopes` was an empty set for Linda (no `.scopes`
        # attr), so issubset() failed for EVERY scoped read tool and the
        # bridge raised 'missing scope'. Empty scope model → skip the check.
        from core.assistant.tools.code import run_python_tool

        res = run_python_tool.invoke(
            {'code': "result = call('platform.circuit_breakers')"},
            agent=Assistant(tools=[]),
            context={},
        )
        out = res.output if hasattr(res, 'output') else res
        self.assertNotIn('missing scope', str(out))

    def test_scope_check_still_enforced_for_scoped_agents(self):
        from core.agents.tools import ToolError
        from core.assistant.tools.code import run_python_tool

        class _ScopedAgent:
            scopes = ['catalog.read']  # does NOT include system.read

        with self.assertRaises(ToolError) as ctx:
            run_python_tool.invoke(
                {'code': "result = call('platform.circuit_breakers')"},
                agent=_ScopedAgent(),
                context={},
            )
        self.assertIn('missing scope', str(ctx.exception))


class _ScriptedProvider:
    """Scripted provider: first turn calls the tool, second turn finishes."""

    name = 'scripted'
    model = 'scripted'

    def __init__(self, tool_name: str, arguments: dict | None = None):
        self._responses = [
            LLMResponse(
                tool_calls=[LLMToolCall(id='c1', name=tool_name, arguments=arguments or {})]
            ),
            LLMResponse(text='done'),
        ]

    def respond(self, **_kw):
        return self._responses.pop(0)


class WriteToolAuditTests(TestCase):
    def _tool(self, *, scopes, name='test.mutate'):
        return Tool(
            name=name,
            description='test write tool',
            handler=lambda **kw: {'ok': True},
            scopes=scopes,
        )

    def test_write_scoped_tool_call_lands_in_core_audit(self):
        from core.audit.models import AuditEvent

        tool = self._tool(scopes=['orders.write'])
        a = Assistant(provider=_ScriptedProvider('test.mutate'), tools=[tool])
        result = a.run(message='mutate it', conversation_key='test:audit-w')
        self.assertEqual(result.state, 'completed')
        ev = AuditEvent.objects.filter(
            event_type='assistant.tool_write', target='test.mutate'
        ).latest('created_at')
        self.assertIn('conversation', ev.metadata)

    def test_read_tools_are_not_audited(self):
        from core.audit.models import AuditEvent

        tool = self._tool(scopes=['orders.read'], name='test.read')
        a = Assistant(provider=_ScriptedProvider('test.read'), tools=[tool])
        a.run(message='read it', conversation_key='test:audit-r')
        self.assertFalse(
            AuditEvent.objects.filter(
                event_type='assistant.tool_write', target='test.read'
            ).exists()
        )


class LegacyMcpShimAuthTests(TestCase):
    LIST_URL = '/api/mcp/tools/list'
    CALL_URL = '/api/mcp/tools/call'

    def test_anonymous_is_rejected(self):
        c = Client()
        self.assertEqual(c.get(self.LIST_URL).status_code, 401)
        self.assertEqual(
            c.post(self.CALL_URL, '{"name": "query_products"}', 'application/json').status_code,
            401,
        )

    def test_staff_can_list(self):
        from django.contrib.auth import get_user_model

        u = get_user_model().objects.create_user(
            username='mcp@x.test', email='mcp@x.test', password='pw', is_staff=True
        )
        c = Client()
        c.force_login(u)
        r = c.get(self.LIST_URL)
        self.assertEqual(r.status_code, 200)
        self.assertIn('tools', r.json())


class DeadTogglesRemovedTests(TestCase):
    def test_unwired_toggles_gone_from_ai_settings_schema(self):
        from plugins.installed.ai_assistant.app import AIAssistantPlugin

        props = AIAssistantPlugin().get_config_schema().get('properties', {})
        self.assertNotIn('agent_purchase_requires_approval', props)
        self.assertNotIn('memory_confidence_decay_days', props)

"""Linda agentic-core hardening (2026-07).

Locks four fixes:
  * run_python's sandbox is READ-ONLY for real — mutating tools that were
    mislabeled `system.read` (memory.remember/forget, skills.record_outcome)
    are no longer script-callable;
  * the bridge's defence-in-depth scope re-check no longer dead-letters
    every scoped read tool for Linda (who has no `.scopes` attribute);
  * (write-tool auditing now lives in core/assistant/gates.py and is tested at
    the MCP edge, agent_mcp/tests/test_linda_turn.py.)
"""

from __future__ import annotations

from django.test import TestCase


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
        # Regression: `agent_scopes` was an empty set for a caller with no
        # `.scopes` attr, so issubset() failed for EVERY scoped read tool and the
        # bridge raised 'missing scope'. No scope model → skip the check. Over
        # MCP (how Linda calls it now) the agent is None; scope was already
        # enforced for run_python itself at the edge.
        from core.assistant.tools.code import run_python_tool

        res = run_python_tool.invoke(
            {'code': "result = call('platform.circuit_breakers')"},
            agent=None,
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


class DeadTogglesRemovedTests(TestCase):
    def test_unwired_toggles_gone_from_ai_settings_schema(self):
        from plugins.installed.ai_assistant.app import AIAssistantPlugin

        props = AIAssistantPlugin().get_config_schema().get('properties', {})
        self.assertNotIn('agent_purchase_requires_approval', props)
        self.assertNotIn('memory_confidence_decay_days', props)

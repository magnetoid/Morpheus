"""workflows.run agent tool — migrated from core/assistant/tools/admin_ops.py
(boundary ratchet). Guards the move: the name resolves for Linda, is registered
once owned by workflows, and the live-run confirm gate still fires."""

from __future__ import annotations

from collections import Counter

from django.test import TestCase

from plugins.installed.workflows.agent_tools import workflows_run_tool

_MIGRATED = ('workflows.run',)


class WorkflowsAgentToolMigrationTests(TestCase):
    def test_plugin_contributes_the_tool(self):
        from plugins.registry import plugin_registry

        names = {t.name for t in plugin_registry.get('workflows').contribute_agent_tools()}
        self.assertTrue(set(_MIGRATED) <= names, f'missing: {set(_MIGRATED) - names}')

    def test_name_registered_once_and_owned_by_workflows(self):
        from core.agents import agent_registry

        for name in _MIGRATED:
            self.assertIsNotNone(agent_registry.get_tool(name), f'{name} not registered')
            self.assertEqual(agent_registry._tool_owners.get(name), 'workflows', f'{name} owner')

    def test_linda_catalog_sources_it_once(self):
        from core.assistant.tools import get_default_tools

        counts = Counter(t.name for t in get_default_tools())
        for name in _MIGRATED:
            self.assertEqual(counts[name], 1, f'{name} appears {counts[name]}x')

    def test_live_run_requires_confirmation(self):
        from core.agents import ToolError

        # dry_run=False without confirmed → the core confirm gate raises
        # before any Workflow lookup, so no fixture is needed.
        with self.assertRaises(ToolError):
            workflows_run_tool.invoke({'name': 'anything', 'dry_run': False})

    def test_unknown_workflow_raises(self):
        from core.agents import ToolError

        with self.assertRaises(ToolError):
            workflows_run_tool.invoke({'name': 'no-such-workflow'})

"""The Worker has no platform internals (v0.199.0).

`gates.DEVELOPER_TOOLS` (reading files and logs on the server, the server's
own facts) are Linda's only in Developer mode, which is for superusers. The
Worker took every tool inside its scopes, these seven included, and any staff
member can start a Worker: through Linda's delegation, an automation, a
workflow, or the agents API. The daily briefing's read-only Worker had them too.
"""

from __future__ import annotations

from django.test import TestCase

from core.agents import agent_registry
from core.assistant.gates import DEVELOPER_TOOLS


class WorkerToolTests(TestCase):
    def _names(self, agent):
        return {tool.name for tool in agent.get_tools()}

    def test_the_worker_is_offered_no_developer_tool(self):
        names = self._names(agent_registry.get_agent('worker'))
        self.assertEqual(sorted(names & DEVELOPER_TOOLS), [])

    def test_the_briefings_read_only_worker_neither(self):
        from core.assistant.briefing import _read_only_worker

        self.assertEqual(sorted(self._names(_read_only_worker()) & DEVELOPER_TOOLS), [])

    def test_a_worker_narrowed_to_skills_neither(self):
        worker = type(agent_registry.get_agent('worker'))()
        worker.uses_skills = ('seo',)
        self.assertEqual(sorted(self._names(worker) & DEVELOPER_TOOLS), [])

    def test_it_keeps_the_stores_tools(self):
        names = self._names(agent_registry.get_agent('worker'))
        for name in ('orders.search', 'products.search', 'help.read', 'errors.recent'):
            self.assertIn(name, names)

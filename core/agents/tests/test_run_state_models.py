"""Run-state models live in core (ADR 0034) — real-manager contract tests.

No mocks: mocks pass while phantom fields/managers fail in prod (the
AI-code-verification rule). These hit the actual relocated models exactly the
way the runtime does — create a run, mirror steps, gate an approval — and lock
the two invariants of the move: the ORIGINAL db_table names, and the back-compat
re-export from plugins.installed.agent_core.models.
"""

from __future__ import annotations

from django.test import TestCase

from core.agents.models import AgentApprovalRequest, AgentRun, AgentStep


class RunStateContractTests(TestCase):
    def test_runtime_persistence_round_trip(self):
        # The exact shapes spawn.py uses: create → step mirror → terminal write.
        run = AgentRun.objects.create(
            agent_name='worker', state='running', user_message='do the thing', metadata={'k': 'v'}
        )
        AgentStep.objects.create(run=run, seq=1, kind='user', content='do the thing')
        AgentStep.objects.create(
            run=run, seq=2, kind='tool_call', name='orders.search', arguments={'q': 'x'}
        )
        run.state = 'completed'
        run.final_text = 'done'
        run.prompt_tokens = 10
        run.completion_tokens = 5
        run.save()

        fresh = AgentRun.objects.get(pk=run.pk)
        self.assertEqual(fresh.state, 'completed')
        self.assertEqual(fresh.total_tokens, 15)
        self.assertEqual(list(fresh.steps.values_list('seq', flat=True)), [1, 2])

    def test_approval_gate_round_trip(self):
        run = AgentRun.objects.create(agent_name='worker', user_message='x')
        req = AgentApprovalRequest.objects.create(
            run=run, tool_name='orders.refund', arguments={'order_number': 'O1'}
        )
        self.assertEqual(req.state, 'pending')
        self.assertEqual(run.approvals.count(), 1)

    def test_db_tables_unchanged(self):
        # The whole point of the state-only move: the live tables keep their
        # original agent_core_* names, so the deploy migration is zero-SQL.
        self.assertEqual(AgentRun._meta.db_table, 'agent_core_agentrun')
        self.assertEqual(AgentStep._meta.db_table, 'agent_core_agentstep')
        self.assertEqual(AgentApprovalRequest._meta.db_table, 'agent_core_agentapprovalrequest')
        self.assertEqual(AgentRun._meta.app_label, 'core')

    def test_agent_core_reexport_is_the_same_class(self):
        # Back-compat: every plugins.installed.agent_core.models import keeps
        # resolving to the SAME model classes (not copies).
        from plugins.installed.agent_core import models as plugin_models

        self.assertIs(plugin_models.AgentRun, AgentRun)
        self.assertIs(plugin_models.AgentStep, AgentStep)
        self.assertIs(plugin_models.AgentApprovalRequest, AgentApprovalRequest)

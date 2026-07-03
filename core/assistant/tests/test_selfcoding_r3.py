"""Release 3 of docs/plans/linda-self-learning-2026-07.md — the self-coding
loop, propose-only: approval queue UI, tool-gap flywheel, evals harness."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from core.agents.llm import LLMResponse, MockLLMProvider
from core.assistant.evals import load_tasks, run_task
from core.assistant.flywheel import run_tool_gap_flywheel
from core.assistant.models import CodeProposal, LindaMemory

_TOOL_SOURCE = (
    'from core.assistant.tools.filesystem import ToolResult, tool\n\n\n'
    "@tool(name='demo.noop', description='demo', scopes=['system.read'],\n"
    "      schema={'type': 'object', 'properties': {}})\n"
    'def demo_noop_tool() -> ToolResult:\n'
    "    return ToolResult(output={'ok': True})\n"
)


def _user(*, superuser: bool):
    return get_user_model().objects.create_user(
        username=f'u{"s" if superuser else "n"}',
        email=f'{"s" if superuser else "n"}@x.test',
        password='pw',
        is_staff=True,
        is_superuser=superuser,
    )


class ProposalQueueAccessTests(TestCase):
    def test_staff_non_superuser_cannot_open_queue(self):
        c = Client()
        c.force_login(_user(superuser=False))
        resp = c.get('/dashboard/assistant/proposals/')
        self.assertEqual(resp.status_code, 302)  # bounced to login

    def test_superuser_sees_queue(self):
        c = Client()
        c.force_login(_user(superuser=True))
        resp = c.get('/dashboard/assistant/proposals/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'code proposals')


class ProposalActionTests(TestCase):
    def setUp(self):
        self.c = Client()
        self.owner = _user(superuser=True)
        self.c.force_login(self.owner)
        self.p = CodeProposal.objects.create(name='demo-noop', source=_TOOL_SOURCE)

    def _post(self, action: str):
        return self.c.post(
            f'/dashboard/assistant/proposals/{self.p.id}/action/', {'action': action}
        )

    def test_reject(self):
        resp = self._post('reject')
        self.assertEqual(resp.status_code, 302)
        self.p.refresh_from_db()
        self.assertEqual(self.p.status, 'rejected')

    def test_approve_records_owner_with_apply_gate_off(self):
        resp = self._post('approve')
        self.assertEqual(resp.status_code, 302)
        self.p.refresh_from_db()
        self.assertEqual(self.p.status, 'approved')
        self.assertEqual(self.p.approver, self.owner.email)
        self.assertEqual(self.p.applied_branch, '')  # gate off → nothing written

    def test_review_stores_consensus(self):
        resp = self._post('review')
        self.assertEqual(resp.status_code, 302)
        self.p.refresh_from_db()
        # No providers configured in tests → panel reports insufficient.
        self.assertEqual(self.p.consensus.get('decision'), 'insufficient')

    def test_unknown_action_is_a_noop(self):
        self._post('detonate')
        self.p.refresh_from_db()
        self.assertEqual(self.p.status, 'draft')

    def test_audit_rows_written(self):
        from core.audit.models import AuditEvent

        self._post('reject')
        self.assertTrue(
            AuditEvent.objects.filter(event_type='assistant.proposal_rejected').exists()
        )


class FlywheelTests(TestCase):
    def _gap(self, key: str, seen: int):
        LindaMemory.objects.create(
            scope='merchant', key=f'tool_gap.{key}', value=f'seen={seen} · {key} capability'
        )

    def _provider(self):
        return MockLLMProvider(responses=[LLMResponse(text=_TOOL_SOURCE)], echo_user=False)

    def test_repeat_gap_becomes_a_draft_proposal(self):
        self._gap('bulk_price_editor', 2)
        out = run_tool_gap_flywheel(provider=self._provider())
        self.assertEqual(out['drafted'], 1)
        p = CodeProposal.objects.get(name='bulk-price-editor')
        self.assertEqual(p.status, 'draft')
        self.assertIn('Auto-drafted from tool gap', p.rationale)

    def test_single_sighting_ignored(self):
        self._gap('rare_thing', 1)
        out = run_tool_gap_flywheel(provider=self._provider())
        self.assertEqual(out.get('drafted', 0), 0)
        self.assertEqual(CodeProposal.objects.count(), 0)

    def test_never_redrafts_an_existing_proposal(self):
        self._gap('bulk_price_editor', 3)
        run_tool_gap_flywheel(provider=self._provider())
        out = run_tool_gap_flywheel(provider=self._provider())
        self.assertEqual(out['drafted'], 0)
        self.assertEqual(CodeProposal.objects.count(), 1)


class EvalsHarnessTests(TestCase):
    def test_golden_tasks_load_and_are_well_formed(self):
        tasks = load_tasks()
        self.assertGreaterEqual(len(tasks), 15)
        for t in tasks:
            self.assertTrue(t.get('name'))
            self.assertTrue(t.get('prompt'))

    def test_task_passes_on_matching_answer(self):
        provider = MockLLMProvider(
            responses=[LLMResponse(text='There are 42 products.')], echo_user=False
        )
        result = run_task(
            {'name': 't', 'prompt': 'count?', 'checks': {'answer_matches': '\\d+'}},
            provider=provider,
        )
        self.assertTrue(result.ok, result.failures)

    def test_task_fails_on_missing_tool_call(self):
        provider = MockLLMProvider(
            responses=[LLMResponse(text='There are 42 products.')], echo_user=False
        )
        result = run_task(
            {'name': 't', 'prompt': 'count?', 'checks': {'tool_called': 'products.count'}},
            provider=provider,
        )
        self.assertFalse(result.ok)
        self.assertIn('products.count', result.failures[0])

    def test_task_fails_on_forbidden_phrase(self):
        provider = MockLLMProvider(
            responses=[LLMResponse(text='As an AI, I cannot check that.')], echo_user=False
        )
        result = run_task(
            {'name': 't', 'prompt': 'x', 'checks': {'answer_not_contains': ['as an AI']}},
            provider=provider,
        )
        self.assertFalse(result.ok)

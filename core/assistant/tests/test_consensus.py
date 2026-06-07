"""Phase 5: multi-model consensus review + Linda-only scoping of self-dev tools."""

from __future__ import annotations

from django.test import SimpleTestCase, TestCase

from core.agents.builtin.worker import Worker
from core.agents.tools import ToolError
from core.assistant.consensus import _parse_verdict, aggregate, evaluate
from core.assistant.models import CodeProposal
from core.assistant.tools import get_default_tools
from core.assistant.tools.code import code_evaluate_proposal_tool


def _v(provider, approve, ok=True, concerns=None):
    return {'provider': provider, 'ok': ok, 'approve': approve, 'concerns': concerns or []}


class AggregateTests(SimpleTestCase):
    def test_insufficient_under_two_valid(self):
        self.assertEqual(aggregate([_v('a', True)])['decision'], 'insufficient')
        self.assertEqual(
            aggregate([_v('a', True), _v('b', True, ok=False)])['decision'], 'insufficient'
        )

    def test_quorum_approves(self):
        out = aggregate([_v('a', True), _v('b', True), _v('c', False)])  # 2/3
        self.assertEqual(out['decision'], 'approved')
        self.assertEqual(out['approvals'], 2)

    def test_below_quorum_rejects(self):
        out = aggregate([_v('a', True), _v('b', False), _v('c', False)])  # 1/3
        self.assertEqual(out['decision'], 'rejected')

    def test_concerns_merged(self):
        out = aggregate([_v('a', False, concerns=['x']), _v('b', False, concerns=['x', 'y'])])
        self.assertEqual(out['concerns'], ['x', 'y'])


class ParseVerdictTests(SimpleTestCase):
    def test_parses_embedded_json(self):
        v = _parse_verdict('a', 'Sure: {"approve": true, "score": 8, "concerns": []} done')
        self.assertTrue(v['ok'] and v['approve'])
        self.assertEqual(v['score'], 8)

    def test_unparseable_marked_not_ok(self):
        v = _parse_verdict('a', 'no json here')
        self.assertFalse(v['ok'])
        self.assertFalse(v['approve'])  # never counts toward quorum


class EvaluateDegradesTests(TestCase):
    def test_insufficient_when_no_providers_configured(self):
        # Test env has no API keys → consensus must defer to human, never approve.
        p = CodeProposal.objects.create(name='x', source='print(1)', findings=[], passed=True)
        out = evaluate(p)
        self.assertEqual(out['decision'], 'insufficient')

    def test_tool_records_consensus_on_proposal(self):
        p = CodeProposal.objects.create(name='y', source='print(1)', findings=[], passed=True)
        res = code_evaluate_proposal_tool.invoke({'proposal_id': str(p.id)})
        self.assertEqual(res.output['decision'], 'insufficient')
        p.refresh_from_db()
        self.assertEqual(p.consensus.get('decision'), 'insufficient')
        self.assertEqual(p.status, 'draft')  # consensus never changes status

    def test_tool_unknown_proposal(self):
        with self.assertRaises(ToolError):
            code_evaluate_proposal_tool.invoke(
                {'proposal_id': '00000000-0000-0000-0000-000000000000'}
            )


class SelfDevScopeTests(SimpleTestCase):
    def test_self_dev_tools_require_selfdev_scope(self):
        # Workers never carry 'selfdev', so these stay Linda-only.
        by_name = {t.name: t for t in get_default_tools()}
        for name in ('code.draft_tool', 'code.evaluate_proposal', 'skills.distill'):
            self.assertIn('selfdev', by_name[name].scopes, name)

    def test_worker_lacks_selfdev_scope(self):
        self.assertNotIn('selfdev', Worker.scopes)

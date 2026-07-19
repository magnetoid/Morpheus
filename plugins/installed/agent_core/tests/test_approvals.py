"""Fail-closed approval resolver + pending recorder (core audit S1)."""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.agents.approval import args_fingerprint
from plugins.installed.agent_core.approvals import record_pending, resolve
from plugins.installed.agent_core.models import AgentApprovalRequest, AgentRun

_TOOL = 'gift_cards.issue'
_ARGS = {'amount': 10, 'to': 'a@b.com'}


class ResolverTests(TestCase):
    def setUp(self):
        self.run = AgentRun.objects.create(agent_name='worker', user_message='go')
        self.ctx = {'agent_run': self.run}

    def _approved(self, *, args=_ARGS, decided_delta=timedelta(0), consumed=False):
        return AgentApprovalRequest.objects.create(
            run=self.run,
            tool_name=_TOOL,
            args_fingerprint=args_fingerprint(_TOOL, args),
            arguments=args,
            state='approved',
            decided_at=timezone.now() - decided_delta,
            consumed_at=timezone.now() if consumed else None,
        )

    def test_denies_without_any_request(self):
        self.assertFalse(resolve(_TOOL, _ARGS, self.ctx))

    def test_denies_pending_request(self):
        AgentApprovalRequest.objects.create(
            run=self.run,
            tool_name=_TOOL,
            args_fingerprint=args_fingerprint(_TOOL, _ARGS),
            arguments=_ARGS,
            state='pending',
        )
        self.assertFalse(resolve(_TOOL, _ARGS, self.ctx))

    def test_approves_and_consumes(self):
        self._approved()
        self.assertTrue(resolve(_TOOL, _ARGS, self.ctx))
        # single-use: the grant is now consumed
        self.assertFalse(resolve(_TOOL, _ARGS, self.ctx))

    def test_expired_grant_denied(self):
        self._approved(decided_delta=timedelta(minutes=10))
        self.assertFalse(resolve(_TOOL, _ARGS, self.ctx))

    def test_fingerprint_mismatch_denied(self):
        # A grant approved for $10 must not authorise a $999 call (injection).
        self._approved(args={'amount': 10, 'to': 'a@b.com'})
        self.assertFalse(resolve(_TOOL, {'amount': 999, 'to': 'a@b.com'}, self.ctx))

    def test_no_run_denied(self):
        self._approved()
        self.assertFalse(resolve(_TOOL, _ARGS, {}))  # no agent_run in context


class RecordPendingTests(TestCase):
    def setUp(self):
        self.run = AgentRun.objects.create(agent_name='worker', user_message='go')

    def test_records_pending_and_pauses_run(self):
        record_pending(tool=_TOOL, arguments=_ARGS, context={'agent_run': self.run})
        req = AgentApprovalRequest.objects.get(run=self.run, tool_name=_TOOL)
        self.assertEqual(req.state, 'pending')
        self.assertEqual(req.args_fingerprint, args_fingerprint(_TOOL, _ARGS))
        self.run.refresh_from_db()
        self.assertEqual(self.run.state, 'awaiting_approval')

    def test_idempotent_single_pending(self):
        for _ in range(3):
            record_pending(tool=_TOOL, arguments=_ARGS, context={'agent_run': self.run})
        self.assertEqual(
            AgentApprovalRequest.objects.filter(run=self.run, state='pending').count(), 1
        )

    def test_no_run_is_noop(self):
        record_pending(tool=_TOOL, arguments=_ARGS, context={})
        self.assertEqual(AgentApprovalRequest.objects.count(), 0)

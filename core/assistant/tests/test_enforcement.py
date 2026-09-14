"""Linda's enforcement stack — scope, budget, deadline, and human consent.

Linda dispatched tools with NO gate until v0.36: her only write-path handling
was a post-hoc audit row, and her dangerous tools (`settings.set`,
`plugins.toggle`, `updates.apply`) trusted an LLM-supplied ``confirmed=True``
argument. Since the model writes that argument, content Linda merely *reads* — a
product description, a log line, a customer note — could induce it. These tests
pin the kernel-side gate that replaced it.

The chain lives in ``core/assistant/gates.py``. Since v0.65.0 its only caller is
the MCP edge a Janus turn goes through (``agent_mcp/linda_turn.py``), which has
end-to-end tests in ``agent_mcp/tests/test_linda_turn.py``; these pin the chain
itself.
"""

from __future__ import annotations

import time

from django.core.cache import cache
from django.test import SimpleTestCase

from core.agents.tools import Tool
from core.assistant import consent, gates
from core.assistant.gates import LINDA_SCOPES


def _tool(name, *, scopes=None, requires_approval=False, supports_staging=False):
    return Tool(
        name=name,
        description=name,
        handler=lambda **kw: {'ok': True},
        schema={'type': 'object', 'properties': {}},
        scopes=list(scopes or []),
        requires_approval=requires_approval,
        supports_staging=supports_staging,
    )


def _gate(tool, *, args=None, context=None, conversation_key='k', human_message='', **kw):
    return gates.gate_reason(
        tool=tool,
        tool_name=tool.name,
        args={} if args is None else args,
        scopes=LINDA_SCOPES,
        context={} if context is None else context,
        conversation_key=conversation_key,
        human_message=human_message,
        **kw,
    )


class ScopeGateTests(SimpleTestCase):
    def test_tool_within_profile_allowed(self):
        self.assertIsNone(_gate(_tool('db.count', scopes=['system.read'])))

    def test_tool_outside_profile_denied(self):
        # A plugin-contributed tool demanding a scope Linda does not hold was
        # previously callable by her — nothing checked.
        reason = _gate(_tool('orders.refund', scopes=['orders.write']))
        self.assertIn('orders.write', reason or '')

    def test_unscoped_tool_allowed(self):
        self.assertIsNone(_gate(_tool('capabilities', scopes=[])))


class BudgetAndDeadlineTests(SimpleTestCase):
    def test_budget_exceeded_blocks(self):
        tool = _tool('db.count', scopes=['system.read'])
        self.assertEqual(_gate(tool, spent_tokens=500, token_budget=100), 'budget_exceeded')

    def test_zero_budget_is_unlimited(self):
        tool = _tool('db.count', scopes=['system.read'])
        self.assertIsNone(_gate(tool, spent_tokens=10_000_000, token_budget=0))

    def test_past_deadline_blocks(self):
        tool = _tool('db.count', scopes=['system.read'])
        reason = _gate(tool, context={'deadline': time.monotonic() - 1})
        self.assertEqual(reason, 'deadline_exceeded')


class HumanConsentGateTests(SimpleTestCase):
    """The core fix: consent is human-attested and kernel-verified."""

    def setUp(self):
        cache.clear()
        self.tool = _tool('settings.set', scopes=['system.write'], requires_approval=True)
        self.args = {'plugin': 'storefront', 'key': 'x', 'value': '1', 'confirmed': True}

    def _gate(self, *, human_message, args=None, context=None):
        return _gate(
            self.tool,
            args=self.args if args is None else args,
            context=context,
            conversation_key='conv-1',
            human_message=human_message,
        )

    def test_llm_supplied_confirmed_flag_is_not_consent(self):
        # THE hole: the model sets confirmed=True itself. First attempt must be
        # refused no matter what the arguments claim.
        reason = self._gate(human_message='disable the reviews plugin')
        self.assertIn('approval_required', reason or '')

    def test_human_yes_after_proposal_allows_once(self):
        self.assertIn('approval_required', self._gate(human_message='change that setting') or '')
        # Human's own turn answers affirmatively → the same call now passes.
        self.assertIsNone(self._gate(human_message='yes'))
        # Single-use: the grant was consumed, so a repeat is gated again.
        self.assertIn('approval_required', self._gate(human_message='yes') or '')

    def test_consent_is_bound_to_exact_arguments(self):
        self._gate(human_message='do it')  # proposes THESE args
        other = dict(self.args, value='999')
        # A "yes" cannot be spent on a call the human never saw.
        self.assertIn('approval_required', self._gate(human_message='yes', args=other) or '')

    def test_negation_wins_over_affirmation(self):
        self._gate(human_message='change that setting')
        self.assertIn('approval_required', self._gate(human_message="yes, but don't") or '')

    def test_staging_tool_exempt_only_in_staged_mode(self):
        staging = _tool(
            'customers.add_note',
            scopes=['customers.write'],
            requires_approval=True,
            supports_staging=True,
        )
        # Staged: the OpsProposal it records IS the sign-off.
        self.assertIsNone(_gate(staging, context={'staged': True}, conversation_key='c'))
        # Not staged: still gated.
        self.assertIn('approval_required', _gate(staging, conversation_key='c') or '')

    def test_non_staging_tool_still_gated_under_staged_context(self):
        # The S1 landmine: a blanket staged exemption lets a tool with no
        # staging branch hard-execute with zero approval.
        reason = self._gate(human_message='', context={'staged': True})
        self.assertIn('approval_required', reason or '')


class ConsentOrderingTests(SimpleTestCase):
    """Consent is spent only by a human message sent AFTER the proposal.

    Without the ordering check, "change the setting, ok?" approves itself: the
    first attempt is refused and recorded, and a retry in the same turn finds the
    turn's own "ok" waiting. The human never saw the proposal.
    """

    def setUp(self):
        cache.clear()
        self.key = dict(conversation_key='conv-order', tool_name='settings.set', args={'k': 1})

    def test_message_older_than_the_proposal_is_not_consent(self):
        sent = time.time()
        consent.request(**self.key)
        self.assertFalse(consent.consume(**self.key, human_message='ok', human_message_at=sent))

    def test_message_after_the_proposal_is_consent(self):
        consent.request(**self.key)
        later = time.time() + 1
        self.assertTrue(consent.consume(**self.key, human_message='yes', human_message_at=later))

    def test_entry_written_before_proposal_times_existed_fails_closed(self):
        from core.agents.approval import args_fingerprint

        fp = args_fingerprint('settings.set', {'k': 1})
        cache.set(consent._key('conv-order', fp), 'pending', 60)
        self.assertFalse(
            consent.consume(**self.key, human_message='yes', human_message_at=time.time())
        )

    def test_gate_passes_the_message_time_through(self):
        tool = _tool('settings.set', scopes=['system.write'], requires_approval=True)
        sent = time.time()
        _gate(
            tool,
            args={'k': 2},
            conversation_key='conv-order',
            human_message='ok',
            human_message_at=sent,
        )
        reason = _gate(
            tool,
            args={'k': 2},
            conversation_key='conv-order',
            human_message='ok',
            human_message_at=sent,
        )
        self.assertIn('approval_required', reason or '')


class WriteAuditTests(SimpleTestCase):
    """Which calls count as writes for `assistant.tool_write`."""

    def test_write_scopes_and_approval_tools_are_writes(self):
        self.assertTrue(gates.is_write_tool(_tool('x', scopes=['orders.write'])))
        self.assertTrue(gates.is_write_tool(_tool('x', scopes=['selfdev'])))
        self.assertTrue(
            gates.is_write_tool(_tool('x', scopes=['system.read'], requires_approval=True))
        )

    def test_reads_are_not(self):
        self.assertFalse(gates.is_write_tool(_tool('x', scopes=['orders.read'])))
        self.assertFalse(gates.is_write_tool(_tool('x')))


class AffirmativeParsingTests(SimpleTestCase):
    def test_affirmatives(self):
        for m in ['yes', 'Yes please', 'yep', 'do it', 'go ahead', 'confirm', 'approved', 'ok']:
            self.assertTrue(consent.is_affirmative(m), m)

    def test_non_affirmatives(self):
        for m in ['no', "don't", 'stop', 'cancel', 'wait', 'not yet', '', 'what does that do?']:
            self.assertFalse(consent.is_affirmative(m), m)

    def test_negation_beats_affirmation(self):
        for m in ['yes but no', "ok don't", 'sure, wait']:
            self.assertFalse(consent.is_affirmative(m), m)

"""Linda's enforcement stack — scope, budget, deadline, and human consent.

Linda dispatched tools with NO gate until v0.36: her only write-path handling
was a post-hoc audit row, and her dangerous tools (`settings.set`,
`plugins.toggle`, `updates.apply`, `code.apply_proposal`) trusted an
LLM-supplied ``confirmed=True`` argument. Since the model writes that argument,
content Linda merely *reads* — a product description, a log line, a customer
note — could induce it. These tests pin the kernel-side gate that replaced it.
"""

from __future__ import annotations

import time

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from core.agents.tools import Tool
from core.assistant import consent
from core.assistant.runtime import Assistant


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


class _Assistant(Assistant):
    """Assistant with the provider/store stubbed — we only exercise the gate."""

    def __init__(self, **kw):
        super().__init__(provider=object(), tools=[], store=_Store(), **kw)


class _Store:
    def append(self, **kw):
        pass

    def history(self, **kw):
        return []


class ScopeGateTests(SimpleTestCase):
    def _gate(self, tool, **kw):
        return _Assistant()._gate_reason(
            tool=tool,
            tool_name=tool.name,
            args={},
            context={},
            conversation_key='k',
            human_message='',
            spent_tokens=0,
            **kw,
        )

    def test_tool_within_profile_allowed(self):
        self.assertIsNone(self._gate(_tool('db.count', scopes=['system.read'])))

    def test_tool_outside_profile_denied(self):
        # A plugin-contributed tool demanding a scope Linda does not hold was
        # previously callable by her — nothing checked.
        reason = self._gate(_tool('orders.refund', scopes=['orders.write']))
        self.assertIn('orders.write', reason or '')

    def test_unscoped_tool_allowed(self):
        self.assertIsNone(self._gate(_tool('capabilities', scopes=[])))


class BudgetAndDeadlineTests(SimpleTestCase):
    def test_budget_exceeded_blocks(self):
        a = _Assistant(token_budget=100)
        reason = a._gate_reason(
            tool=_tool('db.count', scopes=['system.read']),
            tool_name='db.count',
            args={},
            context={},
            conversation_key='k',
            human_message='',
            spent_tokens=500,
        )
        self.assertEqual(reason, 'budget_exceeded')

    def test_zero_budget_is_unlimited(self):
        a = _Assistant(token_budget=0)
        reason = a._gate_reason(
            tool=_tool('db.count', scopes=['system.read']),
            tool_name='db.count',
            args={},
            context={},
            conversation_key='k',
            human_message='',
            spent_tokens=10_000_000,
        )
        self.assertIsNone(reason)

    def test_past_deadline_blocks(self):
        reason = _Assistant()._gate_reason(
            tool=_tool('db.count', scopes=['system.read']),
            tool_name='db.count',
            args={},
            context={'deadline': time.monotonic() - 1},
            conversation_key='k',
            human_message='',
            spent_tokens=0,
        )
        self.assertEqual(reason, 'deadline_exceeded')


class HumanConsentGateTests(SimpleTestCase):
    """The core fix: consent is human-attested and kernel-verified."""

    def setUp(self):
        cache.clear()
        self.tool = _tool('settings.set', scopes=['system.write'], requires_approval=True)
        self.args = {'plugin': 'storefront', 'key': 'x', 'value': '1', 'confirmed': True}

    def _gate(self, *, human_message, args=None, context=None):
        return _Assistant()._gate_reason(
            tool=self.tool,
            tool_name=self.tool.name,
            args=self.args if args is None else args,
            context=context or {},
            conversation_key='conv-1',
            human_message=human_message,
            spent_tokens=0,
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
        a = _Assistant()
        common = {
            'tool': staging,
            'tool_name': staging.name,
            'args': {},
            'conversation_key': 'c',
            'human_message': '',
            'spent_tokens': 0,
        }
        # Staged: the OpsProposal it records IS the sign-off.
        self.assertIsNone(a._gate_reason(context={'staged': True}, **common))
        # Not staged: still gated.
        self.assertIn('approval_required', a._gate_reason(context={}, **common) or '')

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


class InTurnSelfApprovalTests(TestCase):
    """End to end through the loop: a retry cannot spend the turn's own "ok"."""

    def setUp(self):
        cache.clear()

    def test_retry_inside_one_turn_cannot_approve_itself(self):
        from core.agents.llm import LLMResponse, LLMToolCall

        calls = []
        tool = Tool(
            name='settings.set',
            description='settings.set',
            handler=lambda **kw: calls.append(kw) or {'ok': True},
            schema={'type': 'object', 'properties': {}},
            scopes=['system.write'],
            requires_approval=True,
        )

        class _Retrying:
            name = model = 'scripted'

            def __init__(self):
                call = LLMToolCall(id='c1', name='settings.set', arguments={'value': '20'})
                retry = LLMToolCall(id='c2', name='settings.set', arguments={'value': '20'})
                self._r = [
                    LLMResponse(tool_calls=[call]),
                    LLMResponse(tool_calls=[retry]),
                    LLMResponse(text='asked'),
                ]

            def respond(self, **_kw):
                return self._r.pop(0)

        Assistant(provider=_Retrying(), tools=[tool], store=_Store()).run(
            message='set the value to 20, ok?', conversation_key='conv-self-approve'
        )
        self.assertEqual(calls, [])


class RefusalAuditTests(TestCase):
    """A blocked write must leave a trace outside the chat transcript."""

    def test_refused_write_is_audited_with_reason(self):
        from core.agents.llm import LLMResponse, LLMToolCall
        from core.audit.models import AuditEvent

        class _Scripted:
            name = model = 'scripted'

            def __init__(self):
                self._r = [
                    LLMResponse(
                        tool_calls=[LLMToolCall(id='c1', name='test.mutate', arguments={})]
                    ),
                    LLMResponse(text='done'),
                ]

            def respond(self, **_kw):
                return self._r.pop(0)

        # A scope Linda does not hold → refused before invocation.
        tool = _tool('test.mutate', scopes=['orders.write'])
        Assistant(provider=_Scripted(), tools=[tool], store=_Store()).run(
            message='mutate it', conversation_key='test:refusal-audit'
        )
        ev = AuditEvent.objects.filter(
            event_type='assistant.tool_write', target='test.mutate'
        ).latest('created_at')
        self.assertIn('orders.write', ev.metadata.get('error', ''))


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

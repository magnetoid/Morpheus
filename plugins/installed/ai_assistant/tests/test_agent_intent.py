"""Lifecycle tests for the agent intent state machine + signed receipts."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.ai_assistant.models import (
    AgentIntentEvent,
    AgentRegistration,
)
from plugins.installed.ai_assistant.services import intent as intent_service
from plugins.installed.ai_assistant.services.receipts import (
    sign_receipt,
    verify_receipt,
)


def _make_agent(**overrides) -> AgentRegistration:
    defaults = dict(
        agent_id='agent-test-1',
        owner_email='owner@example.com',
        token='tok-1',
        can_browse=True,
        can_purchase=True,
        budget_limit_amount=Decimal('100'),
        purchase_requires_approval=True,
    )
    defaults.update(overrides)
    return AgentRegistration.objects.create(**defaults)


class IntentLifecycleTests(TestCase):
    def test_propose_creates_proposed_intent_with_event(self):
        agent = _make_agent()
        intent = intent_service.propose(
            agent=agent,
            kind='browse',
            summary='Find blenders',
        )
        self.assertEqual(intent.state, 'proposed')
        self.assertEqual(
            list(AgentIntentEvent.objects.filter(intent=intent).values_list('to_state', flat=True)),
            ['proposed'],
        )

    def test_propose_rejects_capability_lacking_kind(self):
        agent = _make_agent(can_purchase=False)
        with self.assertRaises(intent_service.CapabilityDenied):
            intent_service.propose(agent=agent, kind='checkout')

    def test_propose_rejects_over_budget_intent(self):
        agent = _make_agent(budget_limit_amount=Decimal('10'))
        with self.assertRaises(intent_service.BudgetExceeded):
            intent_service.propose(
                agent=agent,
                kind='checkout',
                estimated_cost=Money(50, 'USD'),
            )

    def test_full_lifecycle_emits_signed_receipt(self):
        agent = _make_agent()
        intent = intent_service.propose(
            agent=agent,
            kind='checkout',
            summary='Buy blender',
            estimated_cost=Money(50, 'USD'),
        )
        intent_service.authorize(intent, actor='customer')
        intent.refresh_from_db()
        self.assertEqual(intent.state, 'authorized')

        intent_service.begin_execute(intent)
        intent.refresh_from_db()
        self.assertEqual(intent.state, 'executing')

        result = intent_service.complete(
            intent,
            result={'order_id': 'O-1'},
            actual_cost=Money(49, 'USD'),
        )
        intent.refresh_from_db()
        self.assertEqual(intent.state, 'completed')
        self.assertTrue(intent.receipt_signature)
        # Receipt verifies under the agent secret.
        self.assertTrue(verify_receipt(result.receipt, result.signature, agent.signing_secret))

    def test_invalid_transition_raises(self):
        agent = _make_agent()
        intent = intent_service.propose(agent=agent, kind='browse')
        with self.assertRaises(intent_service.IntentTransitionError):
            intent_service.complete(intent, result={'x': 1})

    def test_receipt_signature_detects_tampering(self):
        agent = _make_agent()
        intent = intent_service.propose(agent=agent, kind='browse')
        intent_service.authorize(intent, actor='customer')
        intent_service.begin_execute(intent)
        result = intent_service.complete(intent, result={'k': 'v'})
        tampered = dict(result.receipt)
        tampered['result'] = {'k': 'tampered'}
        self.assertFalse(verify_receipt(tampered, result.signature, agent.signing_secret))

    def test_receipts_module_round_trips(self):
        agent = _make_agent()
        intent = intent_service.propose(agent=agent, kind='browse')
        payload, signature = sign_receipt(intent, agent.signing_secret)
        self.assertTrue(verify_receipt(payload, signature, agent.signing_secret))
        self.assertFalse(verify_receipt(payload, signature, 'wrong-secret'))

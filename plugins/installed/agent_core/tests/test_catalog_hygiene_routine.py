"""Demo catalog-hygiene routine — staged-changes design §4
(docs/superpowers/specs/2026-07-05-staged-changes-routines-design.md).

Covers the two halves of Task C:

* ``seed_catalog_hygiene_routine`` idempotently creates the paused demo
  BackgroundAgent with the exact spec prompt + staged context overrides.
* ``scheduler.fire`` threads those overrides into the run context, so a
  worker run stages an OpsProposal (with AgentRun provenance) and writes
  NOTHING directly. The staged tool itself is unit-tested in
  core/assistant/tests/test_staged_writes.py — here we drive the wire.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from djmoney.money import Money

from core.agents import LLMResponse, LLMToolCall, MockLLMProvider
from core.assistant.models import OpsProposal
from morpheus.core import agent_registry
from plugins.installed.agent_core import scheduler
from plugins.installed.agent_core.models import AgentRun, BackgroundAgent
from plugins.installed.catalog.agent_tools import products_update_status_tool

SPEC_PROMPT = (
    'Scan the 20 most recently added active products for missing meta '
    'descriptions, empty short descriptions, or missing alt text; STAGE '
    'fixes via your write tools; do not modify anything directly.'
)


def _seeded_routine() -> BackgroundAgent:
    call_command('seed_catalog_hygiene_routine')
    return BackgroundAgent.objects.get(context_overrides__source='routine:catalog-hygiene')


class SeedCommandTests(TestCase):
    def test_seed_creates_routine_per_spec(self):
        bg = _seeded_routine()
        self.assertEqual(bg.agent_name, 'worker')
        self.assertEqual(bg.prompt, SPEC_PROMPT)
        self.assertEqual(
            bg.context_overrides,
            {'staged': True, 'source': 'routine:catalog-hygiene'},
        )
        self.assertEqual(bg.interval_seconds, 86400)
        # Merchant opts in by resuming — matches the default-off
        # AUTONOMY_ENABLED posture (spec §4).
        self.assertEqual(bg.state, BackgroundAgent.STATE_PAUSED)
        self.assertIsNotNone(bg.next_run_at)

    def test_seed_is_idempotent_and_preserves_merchant_edits(self):
        bg = _seeded_routine()
        bg.state = BackgroundAgent.STATE_ACTIVE
        bg.interval_seconds = 3600
        bg.save(update_fields=['state', 'interval_seconds'])

        call_command('seed_catalog_hygiene_routine')

        rows = BackgroundAgent.objects.filter(name=bg.name)
        self.assertEqual(rows.count(), 1)
        bg.refresh_from_db()
        self.assertEqual(bg.state, BackgroundAgent.STATE_ACTIVE)  # not clobbered
        self.assertEqual(bg.interval_seconds, 3600)


class RoutineContextWireTests(TestCase):
    def test_fire_threads_staged_context_into_run_agent(self):
        bg = _seeded_routine()
        fake_result = SimpleNamespace(
            state='completed',
            error='',
            trace=SimpleNamespace(run_id='run-1', prompt_tokens=1, completion_tokens=2),
        )
        with patch(
            'plugins.installed.agent_core.services.run_agent', return_value=fake_result
        ) as run_agent:
            out = scheduler.fire(bg)

        self.assertTrue(out['ok'])
        kwargs = run_agent.call_args.kwargs
        self.assertEqual(kwargs['agent_name'], 'worker')
        self.assertEqual(kwargs['user_message'], SPEC_PROMPT)
        context = kwargs['context']
        self.assertIs(context['staged'], True)
        self.assertEqual(context['source'], 'routine:catalog-hygiene')
        self.assertEqual(context['background_agent_id'], str(bg.id))


class RoutineStagedRunTests(TestCase):
    """Full wire: BackgroundAgent → fire → run_agent → runtime → staged tool.

    The worker's registered write tools migrate to staged mode incrementally
    (spec non-goal); the test registers one staged-capable ecommerce write
    tool the way test_runtime.RegistryTests does, then drives a real run
    with a scripted provider.
    """

    def test_fire_stages_proposal_and_writes_nothing(self):
        from plugins.installed.catalog.models import Product

        product = Product.objects.create(
            name='Hygiene Widget',
            slug='hygiene-widget',
            sku='HYG-1',
            status='active',
            price=Money(Decimal('10.00'), 'USD'),
            # A description keeps ai_assistant's product.created hook from
            # spawning its own (unrelated) autonomous worker run in eager mode.
            description='A widget.',
        )
        bg = _seeded_routine()
        provider = MockLLMProvider(
            [
                LLMResponse(
                    tool_calls=[
                        LLMToolCall(
                            id='1',
                            name='products.update_status',
                            arguments={'id': str(product.id), 'status': 'draft'},
                        )
                    ]
                ),
                LLMResponse(text='Staged one fix.'),
            ]
        )
        agent_registry.register_tool(products_update_status_tool, plugin='__hygiene_test')
        try:
            with patch(
                'plugins.installed.agent_core.services.get_llm_provider', return_value=provider
            ):
                out = scheduler.fire(bg)
        finally:
            agent_registry.drop_plugin('__hygiene_test')

        self.assertTrue(out['ok'])
        self.assertEqual(out['state'], 'completed')

        # ZERO direct writes — the product is untouched…
        product.refresh_from_db()
        self.assertEqual(product.status, 'active')

        # …and exactly one OpsProposal was staged, with routine provenance.
        proposal = OpsProposal.objects.get()
        self.assertEqual(proposal.status, 'proposed')
        self.assertEqual(proposal.kind, 'product.update')
        self.assertEqual(proposal.source, 'routine:catalog-hygiene')
        self.assertEqual(
            proposal.changes,
            [
                {
                    'object': f'catalog.product:{product.pk}',
                    'field': 'status',
                    'old': 'active',
                    'new': 'draft',
                }
            ],
        )

        # Provenance: the proposal points at the AgentRun that staged it
        # (spec §1 agent_run FK; §5 shows that run's cost on the inbox card).
        run = AgentRun.objects.get(user_message=SPEC_PROMPT)
        self.assertEqual(run.state, 'completed')
        self.assertEqual(proposal.agent_run_id, run.id)

"""End-to-end tests for the CRM plugin."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from morpheus.core import agent_registry
from plugins.installed.crm.models import (
    Deal,
    Interaction,
    Lead,
    Pipeline,
)
from plugins.installed.crm.services import (
    advance_deal,
    convert_lead,
    create_followup_task,
    customer_timeline,
    ensure_default_pipeline,
    log_interaction,
    upsert_lead,
)

User = get_user_model()


class LeadServiceTests(TestCase):
    def test_upsert_lead_creates_then_updates(self):
        l1 = upsert_lead(email='Alice@Example.com', first_name='Alice', source='storefront')
        self.assertEqual(l1.email, 'alice@example.com')
        self.assertEqual(l1.status, 'new')
        l2 = upsert_lead(email='alice@example.com', last_name='Wonder', source='referral')
        self.assertEqual(l1.id, l2.id)
        self.assertEqual(l2.last_name, 'Wonder')
        self.assertEqual(l2.source, 'referral')

    def test_convert_lead_records_customer(self):
        lead = upsert_lead(email='b@example.com')
        customer = User.objects.create_user(
            username='bob',
            email='b@example.com',
            password='x',
        )
        convert_lead(lead=lead, customer=customer)
        lead.refresh_from_db()
        self.assertEqual(lead.status, 'converted')
        self.assertEqual(lead.converted_customer_id, customer.id)
        self.assertIsNotNone(lead.converted_at)


class InteractionTests(TestCase):
    def test_log_interaction_attaches_via_generic_fk(self):
        lead = upsert_lead(email='c@example.com')
        i = log_interaction(
            subject=lead,
            kind='note',
            summary='Tested call',
            body='Spoke for 10 min',
            actor_name='alice',
        )
        self.assertEqual(i.subject_id, str(lead.pk))
        self.assertEqual(Interaction.objects.filter(subject_id=str(lead.pk)).count(), 1)

    def test_customer_timeline_returns_only_that_subject(self):
        c1 = User.objects.create_user(username='c1', email='c1@example.com', password='x')
        c2 = User.objects.create_user(username='c2', email='c2@example.com', password='x')
        log_interaction(subject=c1, kind='note', summary='C1 call')
        log_interaction(subject=c2, kind='note', summary='C2 call')
        rows = customer_timeline(c1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].summary, 'C1 call')


class TaskTests(TestCase):
    def test_create_followup_sets_due_at(self):
        c = User.objects.create_user(username='d', email='d@example.com', password='x')
        t = create_followup_task(
            subject=c,
            title='Send sample',
            due_in_hours=12,
            priority='high',
        )
        self.assertEqual(t.title, 'Send sample')
        self.assertEqual(t.priority, 'high')
        self.assertTrue(t.is_open)
        delta = t.due_at - timezone.now()
        self.assertAlmostEqual(delta.total_seconds(), 12 * 3600, delta=120)


class PipelineAndDealTests(TestCase):
    def test_ensure_default_pipeline_creates_six_stages(self):
        pipeline = ensure_default_pipeline()
        self.assertEqual(pipeline.name, 'Default')
        self.assertEqual(pipeline.stages.count(), 6)
        names = list(pipeline.stages.values_list('name', flat=True).order_by('order'))
        self.assertEqual(names, ['Qualified', 'Demo', 'Proposal', 'Negotiation', 'Won', 'Lost'])

    def test_ensure_default_pipeline_is_idempotent(self):
        ensure_default_pipeline()
        ensure_default_pipeline()
        self.assertEqual(Pipeline.objects.filter(name='Default').count(), 1)

    def test_advance_deal_logs_interaction(self):
        pipeline = ensure_default_pipeline()
        qualified = pipeline.stages.get(name='Qualified')
        demo = pipeline.stages.get(name='Demo')
        deal = Deal.objects.create(
            name='Big sale',
            pipeline=pipeline,
            stage=qualified,
            value=Money(Decimal('1000'), 'USD'),
        )
        advance_deal(deal=deal, target_stage='Demo')
        deal.refresh_from_db()
        self.assertEqual(deal.stage_id, demo.id)
        self.assertEqual(
            Interaction.objects.filter(subject_id=str(deal.pk), kind='system').count(),
            1,
        )

    def test_advance_deal_to_won_sets_closed_at(self):
        pipeline = ensure_default_pipeline()
        deal = Deal.objects.create(
            name='Closing',
            pipeline=pipeline,
            stage=pipeline.stages.get(name='Negotiation'),
            value=Money(Decimal('500'), 'USD'),
        )
        self.assertIsNone(deal.closed_at)
        advance_deal(deal=deal, target_stage='Won')
        deal.refresh_from_db()
        self.assertIsNotNone(deal.closed_at)


class HookIntegrationTests(TestCase):
    def test_register_hook_creates_lead_and_logs_interaction(self):
        from morpheus.core import MorpheusEvents, hook_registry

        customer = User.objects.create_user(
            username='reg',
            email='reg@example.com',
            first_name='Reg',
            password='x',
        )
        hook_registry.fire(MorpheusEvents.CUSTOMER_REGISTERED, customer=customer)

        lead = Lead.objects.get(email='reg@example.com')
        self.assertEqual(lead.status, 'converted')
        self.assertEqual(lead.converted_customer_id, customer.id)

        # log_interaction was also fired for the customer
        rows = customer_timeline(customer)
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0].kind, 'system')


class AgentContributionTests(TestCase):
    def test_account_manager_agent_registered(self):
        agent = agent_registry.get_agent('account_manager')
        self.assertIsNotNone(agent)
        self.assertIn('crm.read', agent.scopes)
        self.assertIn('crm.write', agent.scopes)

    def test_crm_tools_registered(self):
        names = {t.name for t in agent_registry.platform_tools()}
        for required in (
            'crm.find_leads',
            'crm.create_lead',
            'crm.log_interaction',
            'crm.list_open_tasks',
            'crm.advance_deal',
            'crm.customer_timeline',
        ):
            self.assertIn(required, names)

    def test_account_manager_can_call_crm_tools(self):
        agent = agent_registry.get_agent('account_manager')
        tool_names = {t.name for t in agent.get_tools()}
        self.assertIn('crm.find_leads', tool_names)
        self.assertIn('crm.log_interaction', tool_names)

    def test_worker_can_call_crm_writes_when_scoped(self):
        # Post-pivot: only one Worker agent, full scope set. CRM writes are
        # bounded by caller scope (token/session) not agent class.
        agent = agent_registry.get_agent('worker')
        tool_names = {t.name for t in agent.get_tools()}
        self.assertIn('crm.create_lead', tool_names)
        self.assertIn('crm.advance_deal', tool_names)


class FindLeadsToolTests(TestCase):
    def test_find_leads_tool_filters(self):
        from plugins.installed.crm.agent_tools import find_leads_tool

        upsert_lead(email='a@example.com', company='Acme')
        upsert_lead(email='b@example.com', company='Beta')
        result = find_leads_tool.invoke({'query': 'acme'})
        emails = [lead['email'] for lead in result.output['leads']]
        self.assertEqual(emails, ['a@example.com'])

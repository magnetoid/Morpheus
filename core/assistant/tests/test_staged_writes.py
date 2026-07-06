"""Staged mode on the ecommerce write tools — staged-changes design §2
(docs/superpowers/specs/2026-07-05-staged-changes-routines-design.md).

When the run context carries ``{'staged': True}`` (set by routines), every
write tool records an OpsProposal instead of executing and tells the LLM
"Staged proposal <id>: <title>". Without that context the behavior is
byte-for-byte unchanged (chat keeps the confirmed/AgentApprovalRequest flow).
"""

# Lazy plugin imports inside helpers are intentional (plugin load-order isolation).
# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from core.assistant.models import OpsProposal
from core.assistant.tools.filesystem import ToolError

STAGED = {'staged': True}


def _product(**kw):
    from plugins.installed.catalog.models import Product

    defaults = {
        'name': 'Widget',
        'slug': 'staged-widget',
        'sku': 'STG-1',
        'status': 'active',
        'price': Money(Decimal('10.00'), 'USD'),
    }
    defaults.update(kw)
    return Product.objects.create(**defaults)


def _order(**kw):
    from plugins.installed.orders.models import Order

    defaults = {
        'email': 'c@example.com',
        'subtotal': Money(Decimal('10'), 'USD'),
        'total': Money(Decimal('10'), 'USD'),
    }
    defaults.update(kw)
    return Order.objects.create(**defaults)


class StagedProductToolTests(TestCase):
    def test_staged_status_change_creates_proposal_and_does_not_mutate(self):
        from core.assistant.tools.ecommerce_writes import products_update_status_tool

        p = _product()
        result = products_update_status_tool.invoke(
            {'id': str(p.id), 'status': 'draft'}, context=dict(STAGED)
        )
        self.assertTrue(str(result.output).startswith('Staged proposal '))
        p.refresh_from_db()
        self.assertEqual(p.status, 'active')  # nothing executed
        proposal = OpsProposal.objects.get()
        self.assertEqual(proposal.status, 'proposed')
        self.assertEqual(proposal.kind, 'product.update')
        self.assertEqual(proposal.source, 'skill:products.update_status')
        self.assertEqual(
            proposal.changes,
            [
                {
                    'object': f'catalog.product:{p.pk}',
                    'field': 'status',
                    'old': 'active',
                    'new': 'draft',
                }
            ],
        )
        self.assertEqual(proposal.target, p)

    def test_staged_context_source_and_agent_run_flow_through(self):
        from core.assistant.tools.ecommerce_writes import products_update_status_tool
        from plugins.installed.agent_core.models import AgentRun

        p = _product(slug='staged-run', sku='STG-RUN')
        run = AgentRun.objects.create(agent_name='worker', user_message='hygiene sweep')
        products_update_status_tool.invoke(
            {'id': str(p.id), 'status': 'archived'},
            context={'staged': True, 'source': 'routine:catalog-hygiene', 'agent_run': run},
        )
        proposal = OpsProposal.objects.get()
        self.assertEqual(proposal.source, 'routine:catalog-hygiene')
        self.assertEqual(proposal.agent_run_id, run.id)

    def test_unstaged_behavior_unchanged(self):
        from core.assistant.tools.ecommerce_writes import products_update_status_tool

        p = _product(slug='unstaged', sku='STG-U')
        # confirmed=False still refuses, exactly as before.
        with self.assertRaises(ToolError):
            products_update_status_tool.invoke({'id': str(p.id), 'status': 'draft'})
        # An empty context (no staged flag) is NOT staged mode.
        with self.assertRaises(ToolError):
            products_update_status_tool.invoke({'id': str(p.id), 'status': 'draft'}, context={})
        # confirmed=True executes directly and stages nothing.
        products_update_status_tool.invoke({'id': str(p.id), 'status': 'draft', 'confirmed': True})
        p.refresh_from_db()
        self.assertEqual(p.status, 'draft')
        self.assertEqual(OpsProposal.objects.count(), 0)

    def test_blocked_class_price_change_returns_error_no_proposal(self):
        from core.assistant.tools.ecommerce_writes import products_update_price_tool

        p = _product(slug='staged-price', sku='STG-PR')
        with self.assertRaises(ToolError) as ctx:
            products_update_price_tool.invoke(
                {'id': str(p.id), 'price': '12.00'}, context=dict(STAGED)
            )
        self.assertIn('safety', str(ctx.exception).lower())
        p.refresh_from_db()
        self.assertEqual(p.price.amount, Decimal('10.00'))
        self.assertEqual(OpsProposal.objects.count(), 0)

    def test_staged_proposal_applies_end_to_end(self):
        from core.assistant.tools.ecommerce_writes import products_update_status_tool

        staff = get_user_model().objects.create_user(username='st', password='x', is_staff=True)
        p = _product(slug='staged-e2e', sku='STG-E2E')
        products_update_status_tool.invoke(
            {'id': str(p.id), 'status': 'archived'}, context=dict(STAGED)
        )
        proposal = OpsProposal.objects.get()
        self.assertTrue(proposal.approve(staff))
        result = proposal.apply(staff)
        self.assertEqual(result['applied'], 1)
        p.refresh_from_db()
        self.assertEqual(p.status, 'archived')


class StagedOrderToolTests(TestCase):
    def test_staged_status_change(self):
        from core.assistant.tools.ecommerce_writes import orders_update_status_tool

        o = _order()
        orders_update_status_tool.invoke(
            {'order_number': o.order_number, 'status': 'confirmed'}, context=dict(STAGED)
        )
        o = type(o).objects.get(pk=o.pk)  # refresh_from_db trips the protected FSM field
        self.assertEqual(o.status, 'pending')
        proposal = OpsProposal.objects.get()
        self.assertEqual(proposal.kind, 'order.update')
        self.assertEqual(
            proposal.changes,
            [
                {
                    'object': f'orders.order:{o.pk}',
                    'field': 'status',
                    'old': 'pending',
                    'new': 'confirmed',
                }
            ],
        )

    def test_staged_cancel_uses_reason_as_summary(self):
        from core.assistant.tools.ecommerce_writes import orders_cancel_tool

        o = _order()
        orders_cancel_tool.invoke(
            {'order_number': o.order_number, 'reason': 'customer asked to cancel'},
            context=dict(STAGED),
        )
        o = type(o).objects.get(pk=o.pk)
        self.assertEqual(o.status, 'pending')
        proposal = OpsProposal.objects.get()
        self.assertEqual(proposal.kind, 'order.cancel')
        self.assertIn('customer asked to cancel', proposal.summary)
        self.assertEqual(proposal.changes[0]['new'], 'cancelled')

    def test_staged_add_note_refuses_without_notes_field(self):
        # orders.Order has no `notes` field today — staging must refuse
        # cleanly instead of recording an un-appliable proposal (the
        # unstaged path fails at save() the same way).
        from core.assistant.tools.ecommerce_writes import orders_add_note_tool

        o = _order()
        with self.assertRaises(ToolError):
            orders_add_note_tool.invoke(
                {'order_number': o.order_number, 'note': 'VIP customer'}, context=dict(STAGED)
            )
        self.assertEqual(OpsProposal.objects.count(), 0)


class StagedCustomerToolTests(TestCase):
    def test_staged_add_note(self):
        from core.assistant.tools.ecommerce_writes import customers_add_note_tool

        u = get_user_model().objects.create_user(
            username='buyer', email='buyer@example.com', password='x'
        )
        customers_add_note_tool.invoke(
            {'email': 'buyer@example.com', 'note': 'prefers email'}, context=dict(STAGED)
        )
        u.refresh_from_db()
        self.assertEqual(u.notes, '')
        proposal = OpsProposal.objects.get()
        self.assertEqual(proposal.kind, 'customer.note')
        self.assertEqual(proposal.changes[0]['object'], f'customers.customer:{u.pk}')
        self.assertEqual(proposal.changes[0]['new'], 'prefers email')


class StagedMetafieldToolTests(TestCase):
    def test_staged_set_updates_existing_row(self):
        from plugins.installed.metafields.agent_tools import metafields_set_tool
        from plugins.installed.metafields.models import Metafield

        p = _product(slug='staged-mf', sku='STG-MF')
        Metafield.objects.set(p, namespace='', key='color', value='red')
        mf = Metafield.objects.get(key='color')
        metafields_set_tool.invoke(
            {
                'model': 'catalog.Product',
                'object_id': str(p.pk),
                'key': 'color',
                'value': 'blue',
            },
            context=dict(STAGED),
        )
        mf.refresh_from_db()
        self.assertEqual(mf.value, 'red')  # untouched
        proposal = OpsProposal.objects.get()
        self.assertEqual(proposal.kind, 'metafield.update')
        self.assertEqual(
            proposal.changes,
            [
                {
                    'object': f'metafields.metafield:{mf.pk}',
                    'field': 'value',
                    'old': 'red',
                    'new': 'blue',
                }
            ],
        )

    def test_staged_set_of_new_key_refuses(self):
        from plugins.installed.metafields.agent_tools import metafields_set_tool

        p = _product(slug='staged-mf-new', sku='STG-MFN')
        with self.assertRaises(ToolError):
            metafields_set_tool.invoke(
                {
                    'model': 'catalog.Product',
                    'object_id': str(p.pk),
                    'key': 'brand-new',
                    'value': 'x',
                },
                context=dict(STAGED),
            )
        self.assertEqual(OpsProposal.objects.count(), 0)

    def test_staged_delete_refuses(self):
        from plugins.installed.metafields.agent_tools import metafields_delete_tool
        from plugins.installed.metafields.models import Metafield

        p = _product(slug='staged-mf-del', sku='STG-MFD')
        Metafield.objects.set(p, namespace='', key='color', value='red')
        with self.assertRaises(ToolError):
            metafields_delete_tool.invoke(
                {
                    'model': 'catalog.Product',
                    'object_id': str(p.pk),
                    'key': 'color',
                    'confirmed': True,
                    'hard_gate_ack': 'YES',
                    'echo': 'color',
                },
                context=dict(STAGED),
            )
        self.assertEqual(OpsProposal.objects.count(), 0)
        self.assertEqual(Metafield.objects.filter(key='color').count(), 1)


class StagedCmsToolTests(TestCase):
    def test_staged_publish_and_unpublish(self):
        from plugins.installed.cms.agent_tools import (
            cms_publish_page_tool,
            cms_unpublish_page_tool,
        )
        from plugins.installed.cms.models import Page

        page = Page.objects.create(title='About', slug='staged-about')
        cms_publish_page_tool.invoke({'slug': 'staged-about'}, context=dict(STAGED))
        page.refresh_from_db()
        self.assertEqual(page.state, 'draft')  # untouched
        proposal = OpsProposal.objects.get()
        self.assertEqual(proposal.kind, 'cms.publish')
        self.assertEqual(proposal.changes[0]['new'], 'published')

        page.state = 'published'
        page.save(update_fields=['state'])
        cms_unpublish_page_tool.invoke({'slug': 'staged-about'}, context=dict(STAGED))
        page.refresh_from_db()
        self.assertEqual(page.state, 'published')  # untouched
        unpub = OpsProposal.objects.filter(kind='cms.unpublish').get()
        self.assertEqual(unpub.changes[0]['new'], 'draft')

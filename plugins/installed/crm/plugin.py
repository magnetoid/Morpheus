"""CRM plugin — leads, accounts, deals, interactions, tasks, an Account Manager agent."""
from __future__ import annotations

import logging

from morpheus import events
from morpheus import Plugin
from morpheus import DashboardPage, SettingsPanel

logger = logging.getLogger('morpheus.crm')


class CrmPlugin(Plugin):
    name = 'crm'
    label = 'CRM'
    version = '1.0.0'
    description = (
        'Customer relationship management: leads, accounts, deals + pipelines, '
        'interactions timeline, follow-up tasks, customer notes, and an '
        'Account Manager agent that drives the day-to-day relationship work.'
    )
    has_models = True
    requires = ['customers', 'orders', 'agent_core']

    def ready(self) -> None:
        self.register_graphql_extension('plugins.installed.crm.graphql.queries')
        self.register_graphql_extension('plugins.installed.crm.graphql.mutations')
        self.register_urls(
            'plugins.installed.crm.urls',
            prefix='dashboard/crm/',
            namespace='crm',
        )

        self.register_hook(events.CUSTOMER_REGISTERED, self.on_customer_registered, priority=70)
        self.register_hook(events.ORDER_PLACED, self.on_order_placed, priority=70)
        self.register_hook(events.CART_ABANDONED, self.on_cart_abandoned, priority=70)

    # ── Hooks ─────────────────────────────────────────────────────────────────

    def on_customer_registered(self, customer, **kwargs):
        """If a lead exists for this email, mark it converted; otherwise create one."""
        if not self.get_config_value('auto_create_lead_on_register', True):
            return
        try:
            from plugins.installed.crm.models import Lead
            from plugins.installed.crm.services import convert_lead, log_interaction, upsert_lead

            email = (getattr(customer, 'email', '') or '').strip().lower()
            if not email:
                return
            existing = Lead.objects.filter(email__iexact=email).first()
            if existing is None:
                existing = upsert_lead(
                    email=email,
                    first_name=getattr(customer, 'first_name', '') or '',
                    last_name=getattr(customer, 'last_name', '') or '',
                    source='storefront',
                )
            convert_lead(lead=existing, customer=customer)
            log_interaction(
                subject=customer, kind='system', direction='internal',
                summary='Customer registered', actor_name='system',
            )
        except Exception as e:  # noqa: BLE001 — never block registration
            logger.warning('crm: customer_registered hook failed: %s', e, exc_info=True)

    def on_order_placed(self, order, **kwargs):
        """Append an order activity row to the customer's timeline."""
        try:
            from plugins.installed.crm.services import log_interaction

            customer = getattr(order, 'customer', None)
            if customer is None:
                return
            log_interaction(
                subject=customer,
                kind='order',
                direction='inbound',
                summary=f'Placed order #{order.order_number} for {order.total}',
                actor_name='system',
                metadata={'order_id': str(order.id), 'order_number': order.order_number,
                          'total': str(getattr(order.total, 'amount', '')),
                          'currency': str(getattr(order.total, 'currency', ''))},
            )
        except Exception as e:  # noqa: BLE001
            logger.warning('crm: order_placed hook failed: %s', e, exc_info=True)

    def on_cart_abandoned(self, cart, **kwargs):
        """Create a 24-hour follow-up task on the customer (if there is one)."""
        if not self.get_config_value('auto_followup_on_abandoned_cart', True):
            return
        try:
            from plugins.installed.crm.services import create_followup_task

            customer = getattr(cart, 'customer', None)
            if customer is None:
                return
            create_followup_task(
                subject=customer,
                title=f'Cart recovery: {customer.email or "customer"}',
                description=f'Cart {cart.id} abandoned. Suggest a personal note or discount.',
                due_in_hours=24,
                priority='normal',
            )
        except Exception as e:  # noqa: BLE001
            logger.warning('crm: cart_abandoned hook failed: %s', e, exc_info=True)

    # ── Contribution surfaces ─────────────────────────────────────────────────

    def contribute_agent_tools(self) -> list:
        from plugins.installed.crm.agent_tools import (
            advance_deal_tool, create_lead_tool, customer_timeline_tool,
            find_leads_tool, list_open_tasks_tool, log_interaction_tool,
        )
        return [
            find_leads_tool, create_lead_tool, log_interaction_tool,
            list_open_tasks_tool, advance_deal_tool, customer_timeline_tool,
        ]

    def contribute_agents(self) -> list:
        from plugins.installed.crm.agents import AccountManagerAgent
        return [AccountManagerAgent()]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='CRM',
                slug='home',
                view='plugins.installed.crm.views.crm_home',
                icon='users-round',
                section='crm',
                order=10,
            ),
            DashboardPage(
                label='Leads',
                slug='leads',
                view='plugins.installed.crm.views.leads_list',
                icon='user-plus',
                section='crm',
                order=20,
            ),
            DashboardPage(
                label='Pipeline',
                slug='pipeline',
                view='plugins.installed.crm.views.pipeline_board',
                icon='kanban',
                section='crm',
                order=30,
            ),
            DashboardPage(
                label='Tasks',
                slug='tasks',
                view='plugins.installed.crm.views.tasks_list',
                icon='list-checks',
                section='crm',
                order=40,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='CRM',
            description='Lead capture, follow-up automation, B2B accounts.',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'auto_create_lead_on_register': {
                    'type': 'boolean', 'default': True,
                    'title': 'Auto-create lead when a customer registers',
                },
                'auto_followup_on_abandoned_cart': {
                    'type': 'boolean', 'default': True,
                    'title': 'Auto-create follow-up task on abandoned cart',
                },
                'enable_b2b_accounts': {
                    'type': 'boolean', 'default': False,
                    'title': 'Enable B2B Accounts UI',
                },
                'default_followup_hours': {
                    'type': 'integer', 'default': 24, 'minimum': 1, 'maximum': 720,
                    'title': 'Default follow-up due window (hours)',
                },
            },
        }

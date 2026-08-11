"""CRM plugin — leads, accounts, deals, interactions, tasks, an Account Manager agent."""

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin, SettingsPanel, StorefrontBlock
from morpheus.core import events

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
        # Public support-chat endpoints for the storefront widget.
        self.register_urls(
            'plugins.installed.crm.urls_storefront',
            prefix='',
            namespace='crm_support',
        )

        self.register_hook(events.CUSTOMER_REGISTERED, self.on_customer_registered, priority=70)
        self.register_hook(events.ORDER_PLACED, self.on_order_placed, priority=70)
        self.register_hook(events.CART_ABANDONED, self.on_cart_abandoned, priority=70)
        # Newsletter signups become Leads (the capture the shadowed storefront
        # view was supposed to do and never did).
        self.register_hook(events.NEWSLETTER_SUBSCRIBED, self.on_newsletter_subscribed, priority=70)
        # Contribute newsletter-signup activity to the dashboard home feed.
        self.register_hook(events.ACTIVITY_FEED, self.on_activity_feed, priority=60)
        self._register_beat_schedule()

    def _register_beat_schedule(self) -> None:
        from celery.schedules import crontab  # noqa: PLC0415
        from django.conf import settings  # noqa: PLC0415

        schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', None)
        if schedule is None:
            return
        schedule.setdefault(
            'crm.poll_mailboxes',
            {
                'task': 'crm.poll_mailboxes',
                'schedule': crontab(minute='*/5'),
            },
        )

    # ── Hooks ─────────────────────────────────────────────────────────────────

    def on_newsletter_subscribed(self, email=None, source='newsletter', **kwargs):
        """NEWSLETTER_SUBSCRIBED → CRM Lead (idempotent, fail-soft)."""
        if not email:
            return
        try:
            from plugins.installed.crm.services import upsert_lead

            upsert_lead(email=email, source='newsletter', metadata={'signup_source': source})
        except Exception as exc:  # noqa: BLE001 — lead capture must never break signup
            import logging

            logging.getLogger('morpheus.crm').warning(
                'newsletter lead capture failed for %s: %s', email, exc, exc_info=True
            )

    def on_activity_feed(self, value, limit=20, **kwargs):
        """Fold recent newsletter signups into the dashboard home feed
        (``ACTIVITY_FEED`` filter). Append own items, return the list.
        """
        from plugins.installed.crm.models import Lead  # noqa: PLC0415

        for lead in Lead.objects.filter(source='newsletter').order_by('-created_at')[:limit]:
            value.append(
                {
                    'kind': 'newsletter',
                    'icon': 'mail',
                    'label': f'Newsletter signup: {lead.email}',
                    'hint': '',
                    'url': f'/dashboard/crm/leads/{lead.id}/',
                    'when': lead.created_at,
                }
            )
        return value

    def on_customer_registered(self, customer, **kwargs):
        """If a lead exists for this email, mark it converted; otherwise create one."""
        if not self.get_config_value('auto_create_lead_on_register', True):
            return
        try:
            from plugins.installed.crm.models import Lead  # noqa: PLC0415
            from plugins.installed.crm.services import (  # noqa: PLC0415
                convert_lead,
                log_interaction,
                upsert_lead,
            )

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
                subject=customer,
                kind='system',
                direction='internal',
                summary='Customer registered',
                actor_name='system',
            )
        except Exception as e:  # noqa: BLE001 — never block registration
            logger.warning('crm: customer_registered hook failed: %s', e, exc_info=True)

    def on_order_placed(self, order, **kwargs):
        """Append an order activity row to the customer's timeline."""
        try:
            from plugins.installed.crm.services import log_interaction  # noqa: PLC0415

            customer = getattr(order, 'customer', None)
            if customer is None:
                return
            log_interaction(
                subject=customer,
                kind='order',
                direction='inbound',
                summary=f'Placed order #{order.order_number} for {order.total}',
                actor_name='system',
                metadata={
                    'order_id': str(order.id),
                    'order_number': order.order_number,
                    'total': str(getattr(order.total, 'amount', '')),
                    'currency': str(getattr(order.total, 'currency', '')),
                },
            )
        except Exception as e:  # noqa: BLE001
            logger.warning('crm: order_placed hook failed: %s', e, exc_info=True)

    def on_cart_abandoned(self, cart, **kwargs):
        """Create a 24-hour follow-up task on the customer (if there is one)."""
        if not self.get_config_value('auto_followup_on_abandoned_cart', True):
            return
        try:
            from plugins.installed.crm.services import create_followup_task  # noqa: PLC0415

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
        from plugins.installed.crm.agent_tools import (  # noqa: PLC0415
            advance_deal_tool,
            create_lead_tool,
            crm_reply_support_tool,
            crm_support_threads_tool,
            customer_timeline_tool,
            find_leads_tool,
            list_open_tasks_tool,
            log_interaction_tool,
        )

        return [
            find_leads_tool,
            create_lead_tool,
            log_interaction_tool,
            list_open_tasks_tool,
            advance_deal_tool,
            customer_timeline_tool,
            crm_support_threads_tool,
            crm_reply_support_tool,
        ]

    def contribute_skills(self) -> list:
        """The CRM skill — opt in via skills=['crm'] for sales-pipeline work.

        Once the account_manager specialist is collapsed (planned), this is
        the durable home of its prompt — same capabilities, runtime composition.
        """
        from core.agents import Skill  # noqa: PLC0415
        from plugins.installed.crm.agent_tools import (  # noqa: PLC0415
            advance_deal_tool,
            create_lead_tool,
            customer_timeline_tool,
            find_leads_tool,
            list_open_tasks_tool,
            log_interaction_tool,
        )

        return [
            Skill(
                name='crm',
                label='CRM Pipeline',
                description='Lead management, deal pipeline, customer timeline.',
                tools=(
                    find_leads_tool,
                    create_lead_tool,
                    log_interaction_tool,
                    list_open_tasks_tool,
                    advance_deal_tool,
                    customer_timeline_tool,
                ),
                system_prompt_prelude=(
                    'You are working on CRM / sales-pipeline tasks. Always:\n'
                    '  • Search for an existing lead before creating a new one — '
                    'duplicates pollute the pipeline.\n'
                    '  • Confirm before advancing a deal stage; that change is '
                    'visible to the whole team.\n'
                    '  • When logging an interaction, include the channel '
                    '(email/call/meeting) and a one-line outcome.'
                ),
            )
        ]

    def contribute_agents(self) -> list:
        from plugins.installed.crm.agents import AccountManagerAgent  # noqa: PLC0415

        return [AccountManagerAgent()]

    def contribute_dashboard_pages(self) -> list:
        # NOTE: 'Leads' page intentionally removed. Contacts (renamed
        # from 'Customers') is the single contact table — every record
        # has a `source` field that distinguishes order customers,
        # signups, lead-form captures, etc. The Lead model remains in
        # place for now to preserve historical data; a follow-up will
        # migrate Lead rows into Customer with source='lead_form'.
        return [
            DashboardPage(
                label='CRM',
                slug='home',
                view='plugins.installed.crm.views.crm_home',
                icon='users-round',
                section='customers',
                order=10,
            ),
            DashboardPage(
                label='Inbox',
                slug='inbox',
                view='plugins.installed.crm.views.inbox_list',
                icon='inbox',
                section='customers',
                order=20,
            ),
            DashboardPage(
                label='Support chat',
                slug='chat',
                view='plugins.installed.crm.chat_views.chat_inbox',
                icon='message-circle',
                section='customers',
                order=25,
                url='/dashboard/crm/chat/',
            ),
            DashboardPage(
                label='Pipeline',
                slug='pipeline',
                view='plugins.installed.crm.views.pipeline_board',
                icon='kanban',
                section='customers',
                order=30,
            ),
            DashboardPage(
                label='Tasks',
                slug='tasks',
                view='plugins.installed.crm.views.tasks_list',
                icon='list-checks',
                section='customers',
                order=40,
            ),
        ]

    def contribute_storefront_blocks(self) -> list:
        # Customer-facing support-chat bubble (replaces the old agent_core
        # "concierge" widget). Disable CRM and the chat disappears.
        return [
            StorefrontBlock(
                slot='global_below_body',
                template='crm/blocks/support_chat.html',
                priority=80,
            ),
        ]

    def contribute_email_templates(self) -> list:
        from morpheus.app import EmailTemplateDef

        return [
            EmailTemplateDef(
                key='crm_support_new_message',
                label='Support chat — new message',
                default_subject='New support message',
                group='CRM',
                description='Sent to staff when a customer needs a reply in support chat.',
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='CRM',
            description='Lead capture, follow-up automation, B2B accounts.',
            schema=self.get_config_schema(),
            category='marketing',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'auto_create_lead_on_register': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Auto-create lead when a customer registers',
                },
                'auto_followup_on_abandoned_cart': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Auto-create follow-up task on abandoned cart',
                },
                'enable_b2b_accounts': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Enable B2B Accounts UI',
                },
                'default_followup_hours': {
                    'type': 'integer',
                    'default': 24,
                    'minimum': 1,
                    'maximum': 720,
                    'title': 'Default follow-up due window (hours)',
                },
            },
        }

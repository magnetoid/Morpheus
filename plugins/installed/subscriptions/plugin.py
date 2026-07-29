"""Subscriptions plugin manifest."""

from __future__ import annotations

from morpheus.core import events
from morpheus.plugin import DashboardPage, Plugin, SettingsPanel, StorefrontBlock


class SubscriptionsPlugin(Plugin):
    name = 'subscriptions'
    label = 'Subscriptions'
    version = '1.0.0'
    description = (
        'Recurring billing + delivery subscriptions: Plan, Subscription '
        '(plan / replenish / curated-box kinds, with lines, shipments, and a '
        'pause/skip/swap audit log), SubscriptionInvoice. Manual provider out '
        'of the box; Stripe Billing adapter slot ready. (Absorbed the parallel '
        'subscriptions_plus plugin, 2026-07-16.)'
    )
    has_models = True
    requires = ['customers']

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.subscriptions.urls',
            prefix='dashboard/subscriptions/',
            namespace='subscriptions',
        )
        # Storefront membership page (plans + subscribe) + the member discount.
        self.register_urls(
            'plugins.installed.subscriptions.urls_storefront',
            prefix='',
            namespace='subscriptions_storefront',
        )
        # Apply the member discount at checkout (live CART_CALCULATE_BREAKDOWN
        # filter — the per-product price hook is dead). Priority 40 = before
        # tax/shipping handlers that read the discounted total.
        from plugins.installed.subscriptions.membership import apply_member_discount

        self.register_hook(events.CART_CALCULATE_BREAKDOWN, apply_member_discount, priority=40)

        # Stripe billing reconciliation: payments fires STRIPE_WEBHOOK_EVENT for
        # every event type it doesn't own; we reconcile the billing subset
        # (invoice.* / customer.subscription.*) onto the local rows. Wired
        # through the bus so payments never imports subscriptions, and the
        # handler self-disables with the plugin (ADR 0023).
        from plugins.installed.subscriptions.webhooks import handle_stripe_event

        self.register_hook(events.STRIPE_WEBHOOK_EVENT, handle_stripe_event)

        # Dunning + pre-renewal email drips (consent-gated, beat-driven).
        self.register_celery_tasks('plugins.installed.subscriptions.tasks')
        self.register_celery_beat(
            'subscriptions.dunning',
            {
                'task': 'plugins.installed.subscriptions.tasks.send_dunning_emails',
                'schedule': 60 * 60,  # hourly — fires each step close to its day
            },
        )
        self.register_celery_beat(
            'subscriptions.prerenewal',
            {
                'task': 'plugins.installed.subscriptions.tasks.send_renewal_reminders',
                'schedule': 60 * 60 * 24,  # daily
            },
        )

    def contribute_storefront_blocks(self) -> list:
        # "Membership" link in the footer's "pages" column (footer_extra slot).
        # Contributed, so it vanishes when the plugin is disabled.
        return [
            StorefrontBlock(
                slot='footer_extra',
                template='subscriptions/blocks/footer_link.html',
                priority=50,
            ),
            # "Subscribe & save" cadence picker on the PDP (absorbed from
            # subscriptions_plus). Self-gates on product.subscription_eligible,
            # so it renders nothing until a product opts in.
            StorefrontBlock(
                slot='pdp_below_form',
                template='subscriptions/blocks/subscribe_save.html',
                priority=15,
                context_keys=['product'],
            ),
        ]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Subscriptions',
                slug='subscriptions',
                view='plugins.installed.subscriptions.views.subscriptions_dashboard',
                icon='repeat',
                section='customers',
                order=70,
            ),
            DashboardPage(
                label='Subscription analytics',
                slug='analytics',
                view='plugins.installed.subscriptions.views_analytics.subscription_analytics',
                icon='trending-up',
                section='analytics',
                order=55,
            ),
        ]

    def contribute_agent_tools(self) -> list:
        from plugins.installed.subscriptions.agent_tools import (
            subscriptions_cancel_tool,
            subscriptions_list_tool,
            subscriptions_pause_tool,
            subscriptions_resume_tool,
        )

        return [
            subscriptions_list_tool,
            subscriptions_pause_tool,
            subscriptions_resume_tool,
            subscriptions_cancel_tool,
        ]

    def contribute_email_templates(self) -> list:
        from morpheus.plugin import EmailTemplateDef

        return [
            EmailTemplateDef(
                key='subscription_payment_failed',
                label='Subscription payment failed (dunning)',
                default_subject='Your subscription payment failed — action needed',
                group='Subscriptions',
                description='Dunning drip sent while a subscription is past due.',
            ),
            EmailTemplateDef(
                key='subscription_upcoming_renewal',
                label='Subscription renews soon',
                default_subject='Your subscription renews soon',
                group='Subscriptions',
                description='Pre-renewal reminder sent a few days before a cycle bills.',
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Subscription billing',
            description='Dunning and pre-renewal email drips for Stripe subscriptions.',
            schema=self.get_config_schema(),
            category='marketing',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'prerenewal_days': {
                    'type': 'integer',
                    'title': 'Pre-renewal reminder lead time (days)',
                    'default': 3,
                    'minimum': 1,
                },
                'dunning_step_days': {
                    'type': 'array',
                    'title': 'Dunning step schedule (days since payment failed)',
                    'items': {'type': 'integer', 'minimum': 0},
                    'default': [0, 3, 7],
                },
                'require_marketing_consent': {
                    'type': 'boolean',
                    'title': 'Only email customers with marketing consent',
                    'default': True,
                },
                # Delivery-subscription knobs (absorbed from subscriptions_plus).
                'default_cadence_days': {
                    'type': 'integer',
                    'default': 30,
                    'title': 'Default delivery cadence (days)',
                },
                'allowed_cadences_days': {
                    'type': 'array',
                    'items': {'type': 'integer'},
                    'default': [14, 30, 45, 60, 90],
                    'title': 'Cadences offered to the shopper',
                },
                'swap_window_days': {
                    'type': 'integer',
                    'default': 2,
                    'title': 'Swap window (days before next ship the customer can swap)',
                },
                'churn_save_prompt': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Show a churn-save prompt on pause / cancel',
                },
            },
        }
